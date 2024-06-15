import re
import requests
import logging
import markdown2
from db import SupabaseInterface


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


# TODO: Optimize
def handle_week_data(comment, issue_url, dmp_id, mentor_name):
    try:
        # Get writer of comment and if it is not the selected mentor, return right away
        writter = "@"+comment['user']['login']
        print(writter)
        print(mentor_name)
        if writter != mentor_name:
            return False

        plain_text_body = markdown2.markdown(comment['body'])

        print(plain_text_body)

        # If weekly goals is not in the body, ignore everything else and return
        if "Weekly Goals" not in plain_text_body:
            return False

        print("Found weekly goals")

        db = SupabaseInterface().get_instance()

        # find matched from issue body
        # TODO: Fix H3 matching only.
        week_matches = re.findall(r'<h3>(Week \d+)</h3>', plain_text_body)
        tasks_per_week = re.findall(
            r'<h3>Week \d+</h3>\s*<ul>(.*?)</ul>', plain_text_body, re.DOTALL)

        weekly_updates = []

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

            print(week_json)

            exist = db.client.table('dmp_week_updates').select(
                "*").eq('dmp_id', week_json['dmp_id']).eq('week', week_json['week']).execute()

            if not exist.data:
                add_data = db.add_data(week_json, 'dmp_week_updates')
            else:
                update_data = db.multiple_update_data(week_json, 'dmp_week_updates', [
                                                      'dmp_id', 'week'], [week_json['dmp_id'], week_json['week']])

            week_json = {}

        return True

    except Exception as e:
        print(e)
        logging.info(f"{e} - find_week_data")
        return False
