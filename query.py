from db import SupabaseInterface

class PostgresQuery:

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
        
        data = SupabaseInterface.postgres_query(query)
        return data
        
    def get_issue_owner(name):
        query = """
            SELECT name, description
            FROM dmp_orgs
            WHERE name = %s;
        """
        data = SupabaseInterface.postgres_query(query,(name,))
        return data
    
    def get_actual_owner_query(owner):
        query = """
            SELECT id, name, repo_owner
            FROM dmp_orgs
            WHERE name LIKE %s;
        """
        
        data = SupabaseInterface.postgres_query(query,(f'%{owner}%',))
        return data
    
     
    def get_dmp_issues(issue_id):
        
        query = """
                SELECT * FROM dmp_issues
                WHERE id = %s;
        """
        data = SupabaseInterface.postgres_query(query,(issue_id,))
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
        
        data = SupabaseInterface.postgres_query(query)
        return data
        
    def get_dmp_issue_updates(dmp_issue_id):

        query = """
                SELECT * FROM dmp_issue_updates
                WHERE dmp_id = %s;
        """
        data = SupabaseInterface.postgres_query(query,(dmp_issue_id,))
        return data
        
    
    def get_pr_data(dmp_issue_id):

        query = """
                SELECT * FROM dmp_pr_updates
                WHERE dmp_id = %s;
        """
        data = SupabaseInterface.postgres_query(query,(dmp_issue_id,))
        return data
    
    def postgres_query_insert(query, params=None):
        try:
            conn = SupabaseInterface.get_postgres_connection()
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
            data = SupabaseInterface.postgres_query(query, (value,))
            
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
            data = SupabaseInterface.postgres_query(query, (dmp_id, week))
            
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
