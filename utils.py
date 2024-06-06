import re,requests


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
    return {"org_id":None,"org_name":None,'org_link':None}

