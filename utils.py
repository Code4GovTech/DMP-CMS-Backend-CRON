import re
import requests
import logging
import markdown2
from db import SupabaseInterface
from query import PostgresQuery

def parse_issue_description(issue_body):
    # Description is everything before goals.
    goals_index = issue_body.find('Goals')
    if goals_index >= 0:
        description = issue_body[:goals_index]
        if 'Description' in description:
            # Remove description from actual description
            description_index = description.find('Description')
            description_index = description_index + 11
            description = description[description_index:]
    else:
        description = ''
    # Remove all #s from description
    description = description.replace('#', '')

    mentor_index = issue_body.find('Mentor')
    if mentor_index >= 0:
        # Next word after mentor is the mentor name
        mentor_contents = issue_body[mentor_index:].split()
        mentor_name = mentor_contents[1]
    else:
        mentor_name = ''
    return {
        'mentor': mentor_name,
        'description': description
    }


def handle_week_data(comment, issue_url, dmp_id, mentor_name):
    try:
        # Get writer of comment and if it is not the selected mentor, return right away
        # writter = "@"+comment['user']['login']
        # if writter != mentor_name:
        #     return False

        plain_text_body = markdown2.markdown(comment['body'])

        # If weekly goals is not in the body, ignore everything else and return
        if "Weekly Goals" not in plain_text_body and "Weekly Learnings" not in plain_text_body:
            return False

        db = SupabaseInterface().get_instance()

        # find matched from issue body
        week_matches = re.findall(r'(<.*?>Week \d+<.*?>)', plain_text_body)
      
        weekly_updates = []
        # Take content after index 0 (first one is a heading)
        tasks_per_week = re.split(r'(<.*?>Week \d+<.*?>)', plain_text_body)[1:]
        tasks_per_week = [tasks_per_week[i] for i in range(1, len(tasks_per_week), 2)]

        for i, week in enumerate(week_matches):
            task_list_html = tasks_per_week[i]
            tasks = re.findall(r'\[(x| )\] (.*?)</li>',
                               task_list_html, re.DOTALL)

            total_tasks = len(tasks)
            completed_tasks = sum(1 for task in tasks if task[0] == 'x')
            task_list = [{"content": i[1], "checked":True if i[0]
                          == 'x' else False} for i in tasks]

            avg = round((completed_tasks / total_tasks)
                        * 100) if total_tasks != 0 else 0

            weekly_updates.append({
                'week': i+1,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'task_html': task_list_html,
                'progress': avg,
                'tasks': task_list
            })
            

        for rec in weekly_updates:
            week_json = {
                "issue_url": issue_url,
                "week": rec['week'],
                "total_task": rec['total_tasks'],
                "completed_task": rec['completed_tasks'],
                "progress": rec['progress'],
                "task_data": rec['task_html'],
                "dmp_id": dmp_id
            }

            exist = db.client.table('dmp_week_updates').select(
                "*").eq('dmp_id', week_json['dmp_id']).eq('week', week_json['week']).execute()
            
            exist = PostgresQuery.check_week_exist(week_json['dmp_id'],week_json['week'])

            if not exist:
                # add_data = db.add_data(week_json, 'dmp_week_updates')
                add_data = PostgresQuery.upsert_data(week_json, 'dmp_week_updates', 'dmp_id')

            else:
                # update_data = db.multiple_update_data(week_json, 'dmp_week_updates', ['dmp_id', 'week'], [week_json['dmp_id'], week_json['week']])
                update_data = PostgresQuery.multiple_update_data(week_json, 'dmp_week_updates', ['dmp_id', 'week'], [week_json['dmp_id'], week_json['week']])

            week_json = {}

        return True

    except Exception as e:
        print(f"Error in week data updates {dmp_id}")
        logging.info(f"{e} - find_week_data")
        return False
