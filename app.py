# app.py
from quart import Quart
import os,markdown2,httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from datetime import datetime,timezone
from query import PostgresORM
from utils import handle_week_data, parse_issue_description
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from models import *
from sqlalchemy.pool import NullPool




# Load environment variables from .env file
load_dotenv()
delay_mins: str = os.getenv("SCHEDULER_DELAY_IN_MINS")
 

app = Quart(__name__)

# Initialize Quart app
app.config['SQLALCHEMY_DATABASE_URI'] = PostgresORM.get_postgres_uri()

# Initialize Async SQLAlchemy
engine = create_async_engine(app.config['SQLALCHEMY_DATABASE_URI'], echo=False,poolclass=NullPool)
async_session = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

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

        # Loop through all dmp issues
        dmp_tickets = await PostgresORM.get_all_dmp_issues(async_session)
        
        for dmp in dmp_tickets:
            dmp_id = dmp['id']            
            print('processing dmp ids ', dmp_id)
            issue_number = dmp['issue_number']
            repo = dmp['repo']
            owner = dmp['repo_owner']

            app.logger.info("DMP_ID: "+str(dmp_id))

            # # Make the HTTP request to GitHub API
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            # 1. Read & Update Description of the ticket
            GITHUB_ISSUE_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            # GITHUB_ISSUE_URL = "https://api.github.com/repos/a2i-code-For-Govstack/Doptor-organogram-builder/issues/1"
            description_url = GITHUB_ISSUE_URL.format(
                owner=owner, repo=repo, issue_number=issue_number)
            async with httpx.AsyncClient() as client:
                issue_response = await client.get(description_url, headers=headers)
                if issue_response.status_code == 200:
                    # Parse issue discription
                    print('processing description ')
                    issue_update = define_issue_description_update(issue_response.json())
                    
                    issue_update['mentor_username'] = dmp['mentor_username']  #get from db
                    issue_update['contributor_username'] = dmp['contributor_username'] #get from db
                    
                    app.logger.info('Decription from remote: ', issue_update)
                    
                    update_data = await PostgresORM.update_dmp_issue(async_session,issue_id=dmp_id, update_data=issue_update)

                    print(f"dmp_issue update works - dmp_id  {dmp_id}") if update_data else print(f"dmp_issue update failed - dmp_id {dmp_id}")
                    app.logger.info(update_data)
                else:
                    print('issue response ', issue_response)
                    app.logger.error("Description API failed: " +
                                     str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))

            # 2. Read & Update comments of the ticket
            page = 1
            while True:
                GITHUB_COMMENTS_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments?page={page}"
                # GITHUB_COMMENTS_URL = "https://github.com/a2i-code-For-Govstack/Doptor-organogram-builder/issues/1/comments?page={page}"
                comments_url = GITHUB_COMMENTS_URL.format(
                    owner=owner, repo=repo, issue_number=issue_number, page=page)
                async with httpx.AsyncClient() as client:
                    comments_response = await client.get(comments_url, headers=headers)
                    if comments_response.status_code == 200:
                        print('processing comments ')
                        week_update_status = False
                        week_learning_status = False
                        # Loop through comments
                        comments_array = comments_response.json()
                        if comments_array == [] or len(comments_array)==0:
                            break
                        for val in comments_response.json():
                            # Handle if any of the comments are week data            
                            plain_text_body = markdown2.markdown(val['body'])
                            if "Weekly Goals" in plain_text_body and not week_update_status:
                                week_update_status = await handle_week_data(val, dmp['issue_url'], dmp_id, issue_update['mentor_username'],async_session)
                            
                            if "Weekly Learnings" in plain_text_body and not week_learning_status:
                                week_learning_status = await handle_week_data(val, dmp['issue_url'], dmp_id, issue_update['mentor_username'],async_session)
                            
                            # Parse comments
                            comment_update = define_issue_update(val, dmp_id=dmp_id)
                            app.logger.info('Comment from remote: ', comment_update)
                            
                            #get created_at                 
                            created_timestamp = await PostgresORM.get_timestamp(async_session, DmpIssueUpdate, 'created_at', 'comment_id', comment_update['comment_id'])
                            comment_update['created_at'] = datetime.utcnow() if not created_timestamp else created_timestamp
                            comment_update['comment_updated_at'] = datetime.utcnow().replace(tzinfo=None)
                            comment_update['created_at']  = comment_update['created_at'].replace(tzinfo=None)
                                                       
                            upsert_comments = await PostgresORM.upsert_data_orm(async_session,comment_update)
                                             
                            print(f"dmp_issue_updates works dmp_id - {dmp_id}") if upsert_comments else print(f"comment failed dmp_id - {dmp_id}")
                            app.logger.info(upsert_comments)
                    else:
                        print('issue response ', issue_response)
                        app.logger.error("Comments API failed: " +
                                        str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))
                        break
                page = page + 1

            # 3. Read & Update PRs of the ticket
            GITHUB_PR_URL = "https://api.github.com/repos/{owner}/{repo}/pulls?state=all"
            pr_url = GITHUB_PR_URL.format(owner=owner, repo=repo)
            async with httpx.AsyncClient() as client:
                pr_response = await client.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                    print('processing prs ')
                    for pr_val in pr_response.json():
                        # Select only those prs which have the issue number in ticket
                        if str(issue_number) not in pr_val['title']:
                            continue
                        pr_created_at = pr_val['created_at']
                        if (pr_created_at >= TARGET_DATE):
                            pr_data = define_pr_update(pr_val, dmp_id)
                            
                            created_timestamp =  await PostgresORM.get_timestamp(async_session,Prupdates,'created_at','pr_id',pr_data['pr_id'])
                            pr_data['created_at'] = datetime.utcnow() if not created_timestamp else created_timestamp
                            pr_data['created_at'] = pr_data['created_at'].replace(tzinfo=None)
                                                       
                            upsert_pr = await PostgresORM.upsert_pr_update(async_session,pr_data)
                            
                            print(f"dmp_pr_updates works - dmp_id is {dmp_id}") if upsert_pr else print(f"dmp_pr_updates failed - dmp_id is {dmp_id}")
                            app.logger.info(upsert_pr)
                else:
                    print('issue response ', issue_response)
                    app.logger.error("PR API failed: " +
                                     str(issue_response.status_code) + " for dmp_id: "+str(dmp_id))
        print(f"last run at - {datetime.utcnow()}")
        return "success"
    except Exception as e:
        print(e)
        print(f"last run with error - {datetime.utcnow()}")
        return "Server Error"


@app.before_serving
async def start_scheduler():
    app.logger.info(
        "Scheduling dmp_updates_job to run every "+delay_mins+" mins")
    scheduler.add_job(dmp_updates, 'interval', minutes=int(delay_mins))
    scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
