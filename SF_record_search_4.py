import json
import subprocess
import logging
from prettytable import PrettyTable

# Configure logging
logging.basicConfig(
    filename="SF_record_search.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def run_command(command, timeout=30):
    """Run a shell command and return the output, handling errors and timeouts."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logging.error(f"Command timed out: {command}")
        return "Error: Command timed out."
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.stderr.strip()}")
        return f"Error: {e.stderr.strip()}"

def authenticate_org(org_alias):
    """Authenticate to the Salesforce org and confirm access."""
    auth_command = f"sfdx force:auth:list --json"
    response = run_command(auth_command)
    if response.startswith("Error:"):
        return False
    try:
        authenticated_orgs = json.loads(response).get("result", [])
        return any(org.get("alias") == org_alias for org in authenticated_orgs)
    except (json.JSONDecodeError, KeyError):
        return False

def fetch_objects(org_alias):
    """Fetch all objects available in the org."""
    command = f"sfdx force:schema:sobject:list --target-org {org_alias} --json"
    response = run_command(command)
    if response.startswith("Error:"):
        return []
    try:
        return json.loads(response).get("result", [])
    except (json.JSONDecodeError, KeyError):
        return []

def describe_object(org_alias, object_name):
    """Fetch and display fields for the specified object."""
    command = f"sfdx sobject:describe -o {org_alias} -s {object_name} --json"
    response = run_command(command)
    if response.startswith("Error:"):
        print("Error: Unable to describe the object.")
        return [], []

    try:
        fields = json.loads(response)["result"]["fields"]
        table = PrettyTable(["Field Name", "Type", "Required"])
        table.align = "l"
        required_fields = []

        for field in fields:
            is_required = "✓" if not field.get("nillable", True) and field.get("createable", False) else ""
            table.add_row([field["name"], field["type"], is_required])
            if is_required:
                required_fields.append(field["name"])

        print("\nAvailable Fields:")
        print(table)
        return [field["name"] for field in fields], required_fields
    except (json.JSONDecodeError, KeyError):
        logging.error("Error parsing describe results.")
        return [], []

def SF_record_search(object_name, target_org, keyword, limit=10, fields=None):
    """Perform a keyword-based record search in Salesforce."""
    if not keyword:
        return "Error: Search keyword is required."
    fields = fields or ["Id", "Name"]
    limit_clause = "" if limit in ["All", "all", None] else f"LIMIT {limit}"

    # Process keywords for robust searching
    keyword_parts = keyword.split()
    keyword_conditions = " OR ".join([f"FIND {{{part}}}" for part in keyword_parts])
    keyword_conditions += f" OR FIND {{{keyword}}}"

    query = f"{keyword_conditions} RETURNING {object_name}({', '.join(fields)} {limit_clause})"
    logging.info(f"Executing query: {query}")

    search_command = f"sfdx force:data:soql:query --query \"{query}\" --target-org {target_org} --json"
    search_results = run_command(search_command)
    if search_results.startswith("Error:"):
        return search_results
    try:
        results = json.loads(search_results).get("result", {}).get("records", [])
        if results:
            table = PrettyTable(fields)
            table.align = "l"
            for record in results:
                row = [record.get(field, "N/A") for field in fields]
                table.add_row(row)
            return table
        return "No records found."
    except (json.JSONDecodeError, KeyError):
        logging.error("Error parsing search results.")
        return "Error: Unable to parse search results."

def main():
    session_state = {}
    while True:
        try:
            print("\nWelcome to SF Record Search!")
            
            # Step 1: Org Alias
            if "org_alias" not in session_state:
                org_alias = input("Enter Salesforce org alias (e.g., MyOrg): ").strip()
                if org_alias.lower() == "start over":
                    session_state.clear()
                    continue
                session_state["org_alias"] = org_alias
            else:
                org_alias = session_state["org_alias"]

            if not authenticate_org(org_alias):
                print("Error: Unable to authenticate. Try again.")
                session_state.pop("org_alias", None)
                continue

            # Step 2: Object Name
            if "object_name" not in session_state:
                object_name = input("Enter the object name (or part of it) to search: ").strip()
                if object_name.lower() == "start over":
                    session_state.clear()
                    continue
                session_state["object_name"] = object_name
            else:
                object_name = session_state["object_name"]

            # Step 3: Fields
            if "fields" not in session_state:
                fields = input("Enter fields to query (comma-separated, or 'all-required'): ").strip()
                if fields.lower() == "start over":
                    session_state.clear()
                    continue
                session_state["fields"] = fields.split(",") if fields.lower() != "all-required" else None
            else:
                fields = session_state["fields"]

            # Step 4: Keyword
            if "keyword" not in session_state:
                keyword = input("Enter keyword to search: ").strip()
                if keyword.lower() == "start over":
                    session_state.clear()
                    continue
                session_state["keyword"] = keyword
            else:
                keyword = session_state["keyword"]

            # Step 5: Limit
            if "limit" not in session_state:
                limit = input("Enter the number of records to return (or 'All' for no limit): ").strip()
                if limit.lower() == "start over":
                    session_state.clear()
                    continue
                session_state["limit"] = None if limit.lower() in ["all", ""] else int(limit)
            else:
                limit = session_state["limit"]

            print("\nSearching...\n")
            result = SF_record_search(object_name, org_alias, keyword, limit, fields)
            print(result)
            break

        except KeyboardInterrupt:
            print("\nExiting. Goodbye!")
            break

if __name__ == "__main__":
    main()






