# app.py
from quart import Quart, jsonify
import httpx,os

from db import SupabaseInterface
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Quart(__name__)

scheduler = AsyncIOScheduler()

@app.route('/')
async def index():
    return 'Hello, World!'


def define_pr_data(pr_val,issue_number,dmp):
    try:
        pr_data = {
            "dmp_id":pr_val['id'],
            "status":pr_val['state'],
            "created_at":pr_val['created_at'],
            "pr_id":pr_val['id'],
            "meta_data":pr_val['title'],
            "html_url":pr_val['html_url'],
            "issue_number":issue_number,
            "url":dmp['url'],
            "pr_updated_at":pr_val['updated_at'],
            "merged_at":pr_val['merged_at'],
            "closed_at":pr_val['closed_at']
        }
         
        return pr_data
    except Exception as e:
        return {}
    
    
def deinfe_issue_data(val,owner,repo,issue_number):
    try:
        dmp_data = {
            "dmp_id":val['id'],
            "owner":owner,
            "repo":repo,
            "issue_number":issue_number,
            "body_text":val['body'],
            "html_body":"",
            "html_url":val['html_url'],
            "comment_id":val['id'],
            "issue_url":val['issue_url'],
            "comment_url":val['url'],
            "comment_updated_at":val['updated_at']
        }
        
        return dmp_data
    except Exception as e:
        return {}
       

@app.route('/my_scheduled_job')
async def my_scheduled_job():
    # Define the GitHub API endpoint URL
    GITHUB_TOKEN =os.getenv('GITHUB_TOKEN')
    try:                    
        target_date =os.getenv('target_date')
        db = SupabaseInterface().get_instance()
        dmp_tickets = db.readAll("dmp_tickets")

        for dmp in dmp_tickets:    
            url_components = dmp["url"].split('/')
            issue_number = url_components[-1]
            repo = url_components[-3]
            owner = url_components[-4]
            
            GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"

            
            url = GITHUB_API_URL.format(owner=owner, repo=repo, issue_number=issue_number)

            # # Make the HTTP request to GitHub API
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)

                # Check if the request was successful
                if response.status_code == 200:
                                      
                    for val in response.json():              
                        pr_created_at = val['created_at']
                        if pr_created_at >= target_date or 1==1:   
                            dmp_data = deinfe_issue_data(val,owner,repo,issue_number)
                            exist = db.client.table('dmp_issue_updates').select("*").eq('dmp_id',dmp_data['dmp_id']).execute()
                            if not exist.data:
                                add_data = db.add_data(dmp_data,'dmp_issue_updates')

            
            #SECOND API CALL
            PR_API_URL = "https://api.github.com/repos/{owner}/{repo}/pulls"
            
            pr_url = PR_API_URL.format(owner=owner, repo=repo)            
            async with httpx.AsyncClient() as client:
                pr_response = await client.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                
                    for pr_val in pr_response.json(): 
                        pr_created_at = pr_val['created_at']
                        if (pr_created_at >= target_date) or 1==1:                   
                            pr_data = define_pr_data(pr_val,issue_number,dmp)
                            exist_pr = db.client.table('dmp_pr_updates').select("*").eq('pr_id',pr_data['pr_id']).execute()
                            if not exist_pr.data:
                                add_data = db.add_data(pr_data,'dmp_pr_updates')
           
        
        return "success"        
                
    except Exception as e:
        print(e)
        return "Server Error"
        



@app.before_serving
async def start_scheduler():
    scheduler.add_job(my_scheduled_job, 'interval', hours=1)
    scheduler.start()

if __name__ == '__main__':
    app.run()

