import re,requests,logging,markdown2
from db import SupabaseInterface


def find_mentors(json,headers):
    try:
        issue_details = json
        
        issue_body = issue_details['body']
        pattern = r"## Mentors\s*([\s\S]+?)\s*##"
        disc_pattern = r"## Desc 1\s*([\s\S]+?)\s*##"
        disc_match = re.search(disc_pattern, issue_body) if issue_body else None
        
        #different patter for find description
        if not disc_match:
            disc_pattern = r"## Description\s*([\s\S]+?)\s*###"
            disc_match = re.search(disc_pattern, issue_body) if issue_body else None
        
        disc_text = disc_match.group(1).strip() if disc_match else None
            
        #different pattern for find mentors
        match = re.search(pattern, issue_body) if issue_body else None
        if not match:
            pattern = r"### Mentor\(s\)\s*([\s\S]+?)\s*###"
            match = re.search(pattern, issue_body) if issue_body else None
            
        if match:
            mentors_text = match.group(1).strip()
            # Extract individual mentor usernames
            mentors = [mentor.strip() for mentor in mentors_text.split(',')]           
        else:
            mentors = []
        api_base_url = "https://api.github.com/users/"

        ment_username = []
        for val in mentors:            
          url = f"{api_base_url}{val[1:]}"
          username = requests.get(url,headers=headers)
          
          ment_username.append(username.json()['login'])
        return {
            'mentors': mentors,
            'mentor_usernames': ment_username,
            'desc':disc_text,
            'title':issue_details['title'],
            'issue_id':issue_details['id'],
            'html_issue_url':issue_details['html_url'],
            'cont_id':issue_details['user']['id'],
            'cont_name':issue_details['user']['login']
        }
    except Exception as e:
        print(e)
        return {
            'mentors': [],
            'mentor_usernames': [],
            'desc':None,
            'title':None,
            'issue_id':None,
            'html_issue_url':None,
            'cont_id':None,
            'cont_name':None
        }



def find_org_data(owner,repo,headers):
  try:
       
    # Fetch repository details to get organization info
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_response = requests.get(repo_url, headers=headers)
    repo_data = repo_response.json()
    if repo_data:
        org_name = repo_data['owner']['login']
        org_id = repo_data['owner']['id']
        org_link = repo_data['owner']['html_url']
        org_desc = repo_data['description']
    else:
        org_name = None
        org_id = None
        org_link = None
        org_desc = repo_data['description']
        
    return {"org_id":org_id,"org_name":org_name,'org_link':org_link,'org_desc':org_desc}
            
  except Exception as e:
    return {"org_id":None,"org_name":None,'org_link':None,'org_desc':None}



def find_pr_number(string):
    try:
        pattern = r'\[#(\d+)\]'        
        # Search the string using the pattern
        match = re.search(pattern, string)
        if match:
            return int(match.group(1))
        else:
            return None
    except Exception as e:
        return ""
    


def find_week_data(html_content,issue_url,dmp_id):
    try:
        db = SupabaseInterface().get_instance()               
        plain_text_body = markdown2.markdown(html_content['body'])

        #find matched from issue body
        week_matches = re.findall(r'<h2>(Week \d+)</h2>', plain_text_body)        
        tasks_per_week = re.findall(r'<h2>Week \d+</h2>\s*<ul>(.*?)</ul>', plain_text_body, re.DOTALL)
        
        weekly_updates = []
        
        for i, week in enumerate(week_matches):
            task_list_html = tasks_per_week[i]
            tasks = re.findall(r'\[(x| )\] (.*?)</li>', task_list_html, re.DOTALL)
            
            total_tasks = len(tasks)
            completed_tasks = sum(1 for task in tasks if task[0] == 'x')
            task_list = [{"content":i[1],"checked":True if i[0]=='x' else False} for i in tasks]

            
            avg = round((completed_tasks / total_tasks) * 100) if total_tasks != 0 else 0
            
            weekly_updates.append({
                'week': i+1,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'task_html':task_list_html,
                'progress': avg,
                'tasks':task_list
            })
        
        for rec in weekly_updates:
            week_json = {
                "issue_url":issue_url,
                "week":rec['week'],
                "total_task":rec['total_tasks'],
                "completed_task":rec['completed_tasks'],
                "progress":rec['progress'],
                "task_data":rec['task_html'],
                "dmp_id":dmp_id
            }
          
            exist = db.client.table('dmp_week_updates').select("*").eq('dmp_id',week_json['dmp_id']).eq('week',week_json['week']).execute()

            if not exist.data:
                add_data = db.add_data(week_json,'dmp_week_updates')
            else:
                update_data =db.multiple_update_data(week_json,'dmp_week_updates',['dmp_id','week'],[week_json['dmp_id'],week_json['week']])
            
            week_json = {}
                    
        return True
                    
    except Exception as e:
        logging.info(f"{e} -find_week_data")
        return False
    
      
  