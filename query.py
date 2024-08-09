from sqlalchemy.future import select
import psycopg2
from models import *
from sqlalchemy import update
# from app import async_session
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import aliased
import os
from psycopg2.extras import RealDictCursor

class PostgresQuery:
    def get_postgres_connection():
        
        # Database configuration
        DB_HOST =os.getenv('POSTGRES_DB_HOST')
        DB_NAME =os.getenv('POSTGRES_DB_NAME')
        DB_USER =os.getenv('POSTGRES_DB_USER')
        DB_PASS =os.getenv('POSTGRES_DB_PASS')
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    
    def postgres_query(query,params=None):        
        try:
            conn = PostgresQuery.get_postgres_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # cursor = conn.cursor()
            if not params:
                cursor.execute(query)
            else:
                cursor.execute(query,params)
             
            try:
                rows = cursor.fetchall()
            except Exception as e:
                rows = []  #only for UPDATE method
               
            results_as_dicts = [dict(row) for row in rows]

            cursor.close()
            conn.close()
            return results_as_dicts       
        
        except Exception as e:            
            print(e)
            pass

    def get_issue_query():
        query = """
            SELECT 
                dmp_orgs.id AS org_id, 
                dmp_orgs.name AS org_name,
                json_agg(
                    json_build_object(
                        'id', dmp_issues.id,
                        'name', dmp_issues.title
                )
                ) AS issues
            FROM 
                dmp_orgs
            LEFT JOIN 
                dmp_issues 
            ON 
                dmp_orgs.id = dmp_issues.org_id
            GROUP BY 
                dmp_orgs.id
            ORDER BY 
               dmp_orgs.id;
        """
        
        data = PostgresQuery.postgres_query(query)
        return data
        
    def get_issue_owner(name):
        query = """
            SELECT name, description
            FROM dmp_orgs
            WHERE name = %s;
        """
        data = PostgresQuery.postgres_query(query)(query,(name,))
        return data
    
    def get_actual_owner_query(owner):
        query = """
            SELECT id, name, repo_owner
            FROM dmp_orgs
            WHERE name LIKE %s;
        """
        
        data = PostgresQuery.postgres_query(query)(query,(f'%{owner}%',))
        return data
    
     
    def get_dmp_issues(issue_id):
        
        query = """
                SELECT * FROM dmp_issues
                WHERE id = %s;
        """
        data = PostgresQuery.postgres_query(query)(query,(issue_id,))
        return data
    
    def get_all_dmp_issues():
        
        query = """SELECT 
            dmp_issues.*,
            json_build_object(
                'created_at', dmp_orgs.created_at,
                'description', dmp_orgs.description,
                'id', dmp_orgs.id,
                'link', dmp_orgs.link,
                'name', dmp_orgs.name,
                'repo_owner', dmp_orgs.repo_owner
            ) AS dmp_orgs
        FROM 
            dmp_issues
        LEFT JOIN 
            dmp_orgs 
        ON 
            dmp_issues.org_id = dmp_orgs.id
        WHERE
            dmp_issues.org_id IS NOT NULL
        ORDER BY 
            dmp_issues.id;


        """
        
        data = PostgresQuery.postgres_query(query)(query)
        return data
        
    def get_dmp_issue_updates(dmp_issue_id):

        query = """
                SELECT * FROM dmp_issue_updates
                WHERE dmp_id = %s;
        """
        data = PostgresQuery.postgres_query(query)(query,(dmp_issue_id,))
        return data
        
    
    def get_pr_data(dmp_issue_id):

        query = """
                SELECT * FROM dmp_pr_updates
                WHERE dmp_id = %s;
        """
        data = PostgresQuery.postgres_query(query)(query,(dmp_issue_id,))
        return data
    
    def postgres_query_insert(query, params=None):
        try:
            conn = PostgresQuery.get_postgres_connection()
            from psycopg2.extras import RealDictCursor

            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if not params:
                cursor.execute(query)
            else:
                cursor.execute(query, params)
            
            # Check if the query is an update/insert/delete or a select
            if query.strip().lower().startswith("select"):
                rows = cursor.fetchall()
                results_as_dicts = [dict(row) for row in rows]
                cursor.close()
                conn.close()
                return results_as_dicts
            else:
                # For update/insert/delete, commit the transaction and close cursor
                conn.commit()
                cursor.close()
                conn.close()
                return True
        
        except Exception as e:
            print(f"An error occurred:postgres_query_insert {e}")
            raise Exception
        
                
    def update_data(data, table_name, match_column, match_value):        
        try:
            # Construct the SQL query
            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
            query = f"UPDATE {table_name} SET {set_clause} WHERE {match_column} = %s"
            
            # Values to update
            values = list(data.values())
            values.append(match_value)
            
            # Execute the query using postgres_query
            PostgresQuery.postgres_query_insert(query, values)
            return True
            
        except Exception as e:
            print(f"An error occurred:update_data {e}")
            return None
            
        
        
        
    def insert_data(data, table_name, match_column, match_value):
        try:
            # Construct the SQL query
            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
            query = f"INSERT INTO {table_name} SET {set_clause} WHERE {match_column} = %s"
            
            # Values to update
            values = list(data.values())
            values.append(match_value)
            
            # Execute the query using postgres_query
            PostgresQuery.postgres_query_insert(query, values)
            
            return values
        except Exception as e:
            print(f"An error occurred:upsert_data {e}")
            return None

    def upsert_data(data, table_name, conflict_column):
        try:
            # Construct the SQL query for UPSERT
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            updates = ', '.join([f"{key} = EXCLUDED.{key}" for key in data.keys()])
            
            query = f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_column})
                DO UPDATE SET {updates}
            """
            
            # Values to insert or update
            values = list(data.values())
            
            # Execute the query using postgres_query
            PostgresQuery.postgres_query_insert(query, values)   
            return values
            
        except Exception as e:
            print(f"An error occurred:upsert_data {e}")
            return None
        

    def get_timestamp(table_name, col_name, col, value):
        try:
            query = f"""
                SELECT {col_name} FROM {table_name}
                WHERE {col} = %s;
            """
            data = PostgresQuery.postgres_query(query, (value,))
            
            if data:
                return data[0][col_name]
            else:
                return None

        except Exception as e:
            print(f"An error occurred:get_timestamp {e}")
            return None
        
    def check_week_exist(dmp_id, week):
        try:
            query = """
                SELECT * FROM dmp_week_updates
                WHERE dmp_id = %s AND week = %s;
            """
            data = PostgresQuery.postgres_query(query)(query, (dmp_id, week))
            
            if data:
                return data
            else:
                return None

        except Exception as e:
            print(f"An error occurred:check_week_exist {e}")
            return None
    
        
    def multiple_update_data(data, table_name, match_columns, match_values):
        try:
            # Construct the SET clause
            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
            
            # Construct the WHERE clause for multiple conditions
            where_clause = " AND ".join([f"{col} = %s" for col in match_columns])
            
            # Combine the clauses into the final query
            query = f"""
                UPDATE {table_name}
                SET {set_clause}
                WHERE {where_clause}
            """
            
            # Values to update followed by the match values
            values = list(data.values()) + match_values
            
            # Execute the query using postgres_query
            val = PostgresQuery.postgres_query_insert(query, values)
            return val
            
        except Exception as e:
            print(f"An error occurred:multiple_update_data {e}")
            raise Exception

       
class PostgresORM:
    
    def get_postgres_uri():
        DB_HOST = os.getenv('POSTGRES_DB_HOST')
        DB_NAME = os.getenv('POSTGRES_DB_NAME')
        DB_USER = os.getenv('POSTGRES_DB_USER')
        DB_PASS = os.getenv('POSTGRES_DB_PASS')
        
        return f'postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
                    
    async def get_all_dmp_issues(async_session):
        try:
            async with async_session() as session:
                # Alias for the DmpOrg table to use in the JSON_BUILD_OBJECT
                dmp_org_alias = aliased(DmpOrg)

                # Build the query
                query = (
                    select(
                        DmpIssue,
                        func.json_build_object(
                            'created_at', dmp_org_alias.created_at,
                            'description', dmp_org_alias.description,
                            'id', dmp_org_alias.id,
                            'link', dmp_org_alias.link,
                            'name', dmp_org_alias.name,
                            'repo_owner', dmp_org_alias.repo_owner
                        ).label('dmp_orgs')
                    )
                    .outerjoin(dmp_org_alias, DmpIssue.org_id == dmp_org_alias.id)
                    .filter(DmpIssue.org_id.isnot(None))
                    .order_by(DmpIssue.id)
                )
                
                # Execute the query and fetch results
                result = await session.execute(query)
                rows = result.fetchall()
                
                # Convert results to dictionaries
                data = []
                for row in rows:
                    issue_dict = row._asdict()  # Convert row to dict
                    dmp_orgs = issue_dict.pop('dmp_orgs')  # Extract JSON object from row
                    issue_dict['dmp_orgs'] = dmp_orgs
                    issue_dict.update(issue_dict['DmpIssue'].to_dict())
                    # Add JSON object back to dict
                    del issue_dict['DmpIssue']
                    data.append(issue_dict)
                    
            return data
            
        except Exception as e:
            print(e)
            raise Exception
        
    async def update_dmp_issue(async_session,issue_id: int, update_data: dict):
        try:
            async with async_session() as session:
                async with session.begin():
                    # Build the update query
                    query = (
                        update(DmpIssue)
                        .where(DmpIssue.id == issue_id)
                        .values(**update_data)
                    )
                    
                    # Execute the query
                    await session.execute(query)
                    await session.commit()
                return True
            
        except Exception as e:
            return False
            
    
    async def upsert_data_orm(async_session, update_data):        
        try:

            async with async_session() as session:
                async with session.begin():
                   
                    # Define the insert statement
                    stmt = insert(DmpIssueUpdate).values(**update_data)

                    # Define the update statement in case of conflict
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['comment_id'],
                        set_={
                            'body_text': stmt.excluded.body_text,
                            'comment_link': stmt.excluded.comment_link,
                            'comment_api': stmt.excluded.comment_api,
                            'comment_updated_at': stmt.excluded.comment_updated_at,
                            'dmp_id': stmt.excluded.dmp_id,
                            'created_by': stmt.excluded.created_by,
                            'created_at': stmt.excluded.created_at
                        }
                    )

                    # Execute the statement
                    await session.execute(stmt)
                    await session.commit()
                    
            return True
                    
        except Exception as e:            
            print(e)
            return False        
        

    
    async def upsert_pr_update(async_session, pr_update_data):
        try:
            async with async_session() as session:
                async with session.begin():
                    pr_update_data['pr_updated_at'] = datetime.fromisoformat(pr_update_data['pr_updated_at']).replace(tzinfo=None) if pr_update_data['pr_updated_at'] else None
                    pr_update_data['merged_at'] = datetime.fromisoformat(pr_update_data['merged_at']).replace(tzinfo=None) if pr_update_data['merged_at'] else None
                    pr_update_data['closed_at'] = datetime.fromisoformat(pr_update_data['closed_at']).replace(tzinfo=None) if pr_update_data['closed_at'] else None

                    # Prepare the insert statement
                    stmt = insert(Prupdates).values(**pr_update_data)

                    # Prepare the conflict resolution strategy
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['pr_id'],  # Assuming `pr_id` is the unique key
                        set_={
                            'status': stmt.excluded.status,
                            'merged_at': stmt.excluded.merged_at,
                            'closed_at': stmt.excluded.closed_at,
                            'pr_updated_at': stmt.excluded.pr_updated_at,
                            'dmp_id': stmt.excluded.dmp_id,
                            'created_at': stmt.excluded.created_at,
                            'title': stmt.excluded.title,
                            'link': stmt.excluded.link
                        }
                    )
                    # Execute and commit the transaction
                    await session.execute(stmt)
                    await session.commit()
                    
                return True
            
        except Exception as e:
            print(e)
            return False
        
        
    
    async def update_dmp_week_update(async_session, update_data):
        try:          
            async with async_session() as session:
                async with session.begin():
                    # Define the filter conditions
                    stmt = (
                        select(DmpWeekUpdate)
                        .where(
                            DmpWeekUpdate.week == update_data['week'],
                            DmpWeekUpdate.dmp_id == update_data['dmp_id']
                        )
                    )

                    # Fetch the row that needs to be updated
                    result = await session.execute(stmt)
                    dmp_week_update = result.scalars().first()

                    if dmp_week_update:
                        # Update the fields with the values from update_data
                        for key, value in update_data.items():
                            setattr(dmp_week_update, key, value)

                        # Commit the changes
                        await session.commit()
                return True
        except Exception as e:
            print(e)
            return False
        
    
    
    async def get_week_updates(async_session, dmp_id, week):
        try:
            async with async_session() as session:
                # Build the ORM query
                stmt = select(DmpWeekUpdate).where(
                    DmpWeekUpdate.dmp_id == dmp_id,
                    DmpWeekUpdate.week == week
                )
                # Execute the query
                result = await session.execute(stmt)
                
                # Fetch all matching rows
                week_updates = result.scalars().all()
                

            return True if len(week_updates)>0 else False
        
        except Exception as e:
            return False    
        
    
    
    async def insert_dmp_week_update(async_session, update_data):
        try:
            async with async_session() as session:
                async with session.begin():
                    # Define the insert statement
                    stmt = insert(DmpWeekUpdate).values(**update_data)

                    # Execute the statement
                    await session.execute(stmt)
                    await session.commit()

                return True

        except Exception as e:
            print(e)
            return False
        
    
