# app.py
from quart import Quart, jsonify
import httpx,os

from db import SupabaseInterface
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from datetime import datetime

from utils import find_mentors, find_org_data

# Load environment variables from .env file
load_dotenv()

app = Quart(__name__)

scheduler = AsyncIOScheduler()

@app.route('/')
async def index():
    return 'Hello, World!'


def define_pr_data(pr_val,issue_number,dmp,owner,repo):
    try:
        pr_data = {
            "dmp_id":pr_val['id'],
            "status":pr_val['state'],
            "created_at":pr_val['created_at'],
            "pr_id":pr_val['id'],
            "meta_data":pr_val['title'],
            "html_url":pr_val['html_url'],
            "issue_number":issue_number,
            "url":dmp['repo_url'],
            "pr_updated_at":pr_val['updated_at'],
            "merged_at":pr_val['merged_at'],
            "closed_at":pr_val['closed_at'],
            "owner":owner,
            "repo":repo
        }
         
        return pr_data
    except Exception as e:
        print(e)
        return {}
    
    
def define_issue_data(val,owner,repo,issue_number,dmp):
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
            "issue_url":val['issue_url'] if 'issue_url' in val else val['url'],
            "comment_url":val['comments_url'] if 'comments_url' in val else val['url'],
            "comment_updated_at":val['updated_at'],
            "mentor_name":val['mentor_usernames'],
            "mentor_id":val['mentors'],
            "contributor_name":val['cont_name'],
            "contributor_id":val['cont_id'],
            "title":val['title'],
            "description":val['desc'],
            "html_issue_url":val['html_issue_url'],
            "org_id":val['org_id'],
            "org_name":val['org_name'],
            "org_link":val['org_link'],
            "dmp_issue_url":dmp['repo_url'],
            "org_description":val['org_desc']
            

        }
        
        return dmp_data
    except Exception as e:
        return {}
       

@app.route('/my_scheduled_job')
async def my_scheduled_job():
    print(f"job started --- {datetime.now()}")
    # Define the GitHub API endpoint URL
    GITHUB_TOKEN =os.getenv('APP_DEV_GITHUB_TOKEN')
    try:                    
        TARGET_DATE =os.getenv('APP_DEV_TARGET_DATE')
        db = SupabaseInterface().get_instance()
        dmp_tickets = db.readAll("dmp_issues")

        for dmp in dmp_tickets:    
            url_components = dmp["repo_url"].split('/')
            issue_number = url_components[-1]
            repo = url_components[-3]
            owner = url_components[-4]
            
            # # Make the HTTP request to GitHub API
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
            
            #save first comment of issues
            GITHUB_COMMENT_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            comment_url = GITHUB_COMMENT_URL.format(owner=owner, repo=repo, issue_number=issue_number)

            async with httpx.AsyncClient() as client:
                comment_response = await client.get(comment_url, headers=headers)
                dmp_data = define_issue_data(comment_response.json(),owner,repo,issue_number)
                exist = db.client.table('dmp_issue_updates').select("*").eq('dmp_id',dmp_data['dmp_id']).execute()
                if not exist.data:
                    add_data = db.add_data(dmp_data,'dmp_issue_updates')
            

            
            url = GITHUB_API_URL.format(owner=owner, repo=repo, issue_number=issue_number)

           
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)

                # Check if the request was successful
                if response.status_code == 200:
                                      
                    for val in response.json():              
                        pr_created_at = val['created_at']
                        if pr_created_at >= TARGET_DATE or 1==1:   
                            dmp_data = define_issue_data(val,owner,repo,issue_number)
                            exist = db.client.table('dmp_issue_updates').select("*").eq('dmp_id',dmp_data['dmp_id']).execute()
                            if not exist.data:
                                add_data = db.add_data(dmp_data,'dmp_issue_updates')
                            else:
                                update_data =db.update_data(dmp_data,'dmp_issue_updates','dmp_id',dmp_data['dmp_id'])

            
            #SECOND API CALL
            PR_API_URL = "https://api.github.com/repos/{owner}/{repo}/pulls"
            
            pr_url = PR_API_URL.format(owner=owner, repo=repo)            
            async with httpx.AsyncClient() as client:
                pr_response = await client.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                
                    for pr_val in pr_response.json(): 
                        pr_created_at = pr_val['created_at']
                        if (pr_created_at >= TARGET_DATE) or 1==1:                   
                            pr_data = define_pr_data(pr_val,issue_number,dmp)
                            exist_pr = db.client.table('dmp_pr_updates').select("*").eq('pr_id',pr_data['pr_id']).execute()
                            if not exist_pr.data:
                                add_data = db.add_data(pr_data,'dmp_pr_updates')
                            else:
                                add_data = db.update_data(pr_data,'dmp_pr_updates','pr_id',pr_data['pr_id'])
                                
           
        
        return "success"        
                
    except Exception as e:
        print(e)
        return "Server Error"
        




@app.route('/dmp_updates')
async def dmp_updates():
    print(f"job started --- {datetime.now()}")
    # Define the GitHub API endpoint URL
    GITHUB_TOKEN =os.getenv('APP_DEV_GITHUB_TOKEN')
    TARGET_DATE =os.getenv('APP_DEV_TARGET_DATE')
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:                    
        db = SupabaseInterface().get_instance()
        dmp_tickets = db.readAll("dmp_issues")
        
        for dmp in dmp_tickets:    
            url_components = dmp["repo_url"].split('/')
            issue_number = url_components[-1]
            repo = url_components[-3]
            owner = url_components[-4]
                        
            GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
            #save first comment of issues
            GITHUB_COMMENT_URL = "https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            comment_url = GITHUB_COMMENT_URL.format(owner=owner, repo=repo, issue_number=issue_number)

            async with httpx.AsyncClient() as client:
                comment_response = await client.get(comment_url, headers=headers)
                
                #find mentors and organization datas                                
                ment_data = find_mentors(comment_response.json())
                org_data = find_org_data(owner,repo,headers)
                
                issue_value = comment_response.json()
                issue_value.update(ment_data)
                issue_value.update(org_data)
                
              
                dmp_data = define_issue_data(issue_value,owner,repo,issue_number,dmp)
                #SAVE FIRST COMMENT OF THE ISSUE ONLY HERE
                exist = db.client.table('dmp_issue_updates').select("*").eq('dmp_id',dmp_data['dmp_id']).execute()
                if not exist.data:
                    add_data = db.add_data(dmp_data,'dmp_issue_updates')                    
                else:
                    update_data =db.update_data(dmp_data,'dmp_issue_updates','dmp_id',dmp_data['dmp_id'])
        
            
            url = GITHUB_API_URL.format(owner=owner, repo=repo, issue_number=issue_number)
                       
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                # SAVE REMAINING COMMENT OF THE ISSUE BELOW
                if response.status_code == 200:
                                      
                    for val in response.json(): 
                        val.update(org_data)   
                        val.update(ment_data)     
                        pr_created_at = val['created_at']
                        if pr_created_at >= TARGET_DATE or 1==1:   
                            dmp_data = define_issue_data(val,owner,repo,issue_number,dmp)
                                                        
                            exist = db.client.table('dmp_issue_updates').select("*").eq('dmp_id',dmp_data['dmp_id']).execute()
                            if not exist.data:
                                add_data = db.add_data(dmp_data,'dmp_issue_updates')
                            else:
                                update_data =db.update_data(dmp_data,'dmp_issue_updates','dmp_id',dmp_data['dmp_id'])

            #SECOND API CALL - PR
            PR_API_URL = "https://api.github.com/repos/{owner}/{repo}/pulls"
            
            pr_url = PR_API_URL.format(owner=owner, repo=repo)            
            async with httpx.AsyncClient() as client:
                pr_response = await client.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                
                    for pr_val in pr_response.json(): 
                        pr_created_at = pr_val['created_at']
                        if (pr_created_at >= TARGET_DATE) or 1==1:                   
                            pr_data = define_pr_data(pr_val,issue_number,dmp,owner,repo)
                            exist_pr = db.client.table('dmp_pr_updates').select("*").eq('pr_id',pr_data['pr_id']).execute()
                            if not exist_pr.data:
                                add_data = db.add_data(pr_data,'dmp_pr_updates')
                            else:
                                update_data = db.update_data(pr_data,'dmp_pr_updates','pr_id',pr_data['pr_id'])
                                
           
        
        return "success"        
                
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(e)
        return f"Server Error --{error_traceback}"
        



@app.before_serving
async def start_scheduler():
    scheduler.add_job(dmp_updates, 'interval', minutes=2)
    scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0')

