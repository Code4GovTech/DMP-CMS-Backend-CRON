# app.py
from quart import Quart
import httpx
import os,markdown2
from db import SupabaseInterface
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from datetime import datetime

from utils import handle_week_data, parse_issue_description

# Load environment variables from .env file
load_dotenv()
delay_mins: str = os.getenv("SCHEDULER_DELAY_IN_MINS")

app = Quart(__name__)

scheduler = AsyncIOScheduler()


@app.route('/')
async def index():
    return 'Hello, World!'


def define_issue_description_update(val):
    try:
        parsed_body = parse_issue_description(val['body'])
        # Get contributor from assignee
        assignee = val['assignee']
        if assignee is not None:
            contributor = assignee['login']
        else:
            contributor = ''
        issue_update = {
            "mentor_username": parsed_body['mentor'],
            "contributor_username": contributor,
            "title": val['title'],
            "description": parsed_body['description']
        }
        return issue_update
    except Exception as e:
        print(e)
        return {}


def define_issue_update(val, dmp_id):
    try:
        issue_update = {
            "dmp_id": dmp_id,
            "body_text": val['body'],
            "comment_id": val['id'],
            "comment_updated_at": val['updated_at'],
            "comment_link": val['html_url'],
            "comment_api": val['comments_url'] if 'comments_url' in val else val['url'],
            "created_by": val['user']['login']
        }
        return issue_update
    except Exception as e:
        print(e)
        return {}


def define_pr_update(pr_val, dmp_id):
    try:
        pr_data = {
            "dmp_id": dmp_id,
            "pr_id": pr_val['id'],
            "pr_updated_at": pr_val['updated_at'],
            "status": pr_val['state'],
            "merged_at": pr_val['merged_at'],
            "closed_at": pr_val['closed_at'],
            "created_at": pr_val['created_at'],
            "title": pr_val['title'],
            "link": pr_val['html_url']
        }

        return pr_data
    except Exception as e:
        print(e)
        return {}


@app.route('/dmp_updates')
async def dmp_updates():
    print(
        f"Issue description, comments and PR job started --- {datetime.now()}")
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    try:
        TARGET_DATE = os.getenv('TARGET_DATE')
        db = SupabaseInterface().get_instance()

        # Loop through all dmp issues
        dmp_tickets = db.get_dmp_issues()

        for dmp in dmp_tickets:
            dmp_id = dmp['id']
            issue_number = dmp['issue_number']
            repo = dmp['repo']
            owner = dmp['dmp_orgs']['name']

            app.logger.info("DMP_ID: "+str(dmp_id))

            # # Make the HTTP request to GitHub API
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            # 1. Read & Update Description of the ticket
            GITHUB_ISSUE_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            description_url = GITHUB_ISSUE_URL.format(
                owner=owner, repo=repo, issue_number=issue_number)

            async with httpx.AsyncClient() as client:
                issue_response = await client.get(description_url, headers=headers)
                if issue_response.status_code == 200:
                    # Parse issue discription
                    issue_update = define_issue_description_update(
                        issue_response.json())
                    
                    issue_update['mentor_username'] = dmp['mentor_username']  #get from db
                    issue_update['contributor_username'] = dmp['contributor_username'] #get from db
                    
                    app.logger.info('Decription from remote: ', issue_update)
                    update_data = db.update_data(
                        issue_update, 'dmp_issues', 'id', dmp_id)
                    app.logger.info(update_data)
                else:
                    app.logger.error("Description API failed: " +
                                     str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))

            # 2. Read & Update comments of the ticket
            GITHUB_COMMENTS_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
            comments_url = GITHUB_COMMENTS_URL.format(
                owner=owner, repo=repo, issue_number=issue_number)
            async with httpx.AsyncClient() as client:
                comments_response = await client.get(comments_url, headers=headers)
                if comments_response.status_code == 200:
                    week_update_status = False
                    # Loop through comments
                    for val in comments_response.json():
                        # Handle if any of the comments are week data                        
                        plain_text_body = markdown2.markdown(val['body'])
                        if "Weekly Goals" in plain_text_body and not week_update_status:
                            week_update_status = handle_week_data(val, dmp['issue_url'], dmp_id, issue_update['mentor_username'])
                        
                        # Parse comments
                        comment_update = define_issue_update(
                            val, dmp_id=dmp_id)
                        app.logger.info(
                            'Comment from remote: ', comment_update)
                        upsert_comments = db.upsert_data(
                            comment_update, 'dmp_issue_updates')
                        app.logger.info(upsert_comments)
                else:
                    app.logger.error("Comments API failed: " +
                                     str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))

            # 3. Read & Update PRs of the ticket
            GITHUB_PR_URL = "https://api.github.com/repos/{owner}/{repo}/pulls"
            pr_url = GITHUB_PR_URL.format(owner=owner, repo=repo)
            async with httpx.AsyncClient() as client:
                pr_response = await client.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                    for pr_val in pr_response.json():
                        # Select only those prs which have the issue number in ticket
                        if "#"+str(issue_number) not in pr_val['title']:
                            continue
                        pr_created_at = pr_val['created_at']
                        if (pr_created_at >= TARGET_DATE) or 1 == 1:
                            pr_data = define_pr_update(pr_val, dmp_id)
                            upsert_pr = db.upsert_data(
                                pr_data, 'dmp_pr_updates')
                            app.logger.info(upsert_pr)
                else:
                    app.logger.error("PR API failed: " +
                                     str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))
        return "success"
    except Exception as e:
        print(e)
        return "Server Error"


@app.before_serving
async def start_scheduler():
    app.logger.info(
        "Scheduling dmp_updates_job to run every "+delay_mins+" mins")
    scheduler.add_job(dmp_updates, 'interval', minutes=int(delay_mins))
    scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
