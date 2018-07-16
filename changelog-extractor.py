"""Script parses changelog from git based on 2 latest tags, formates changelog to .md format, creates/updates release on gitlab, posts to slack
"""
import subprocess
import os

def get_md_formatted_changelog(new_commit, old_commit) : 
    #saving parameters this way to make sure that they are read properly on bash command
    get_log_format = '%x1f'.join(['%b', '%h']) + '%x1e'
    bash_command = 'git --no-pager --git-dir=.git log --first-parent --format="%s"' % get_log_format   + " "+ new_commit+"..." + old_commit
    #getting raw changelog from git
    raw_changelog = run_command(bash_command).replace("\"", "")
    return  convert_changelog_text_to_md(raw_changelog, None)

def build_command_for_tag_notes(reqType, clean_changelog, tag) : 
    formatted_project_path = os.environ['CI_PROJECT_PATH'].replace("/","%2F")  
    return 'curl  -X '+reqType+'  --header "PRIVATE-TOKEN: $GITLAB_API_PRIVATE_TOKEN" -d description="'+clean_changelog+ '" https://git.smarpsocial.com/api/v4/projects/"'+ formatted_project_path+ '"/repository/tags/"'+tag+'"/release'
     
def put_tag_notes_on_gitlab( clean_changelog  , tag):
    # create a release notes just in case it hasnt'been created before
    k = os.system(build_command_for_tag_notes("POST", clean_changelog, tag))
    # updating just in case it had been created before
    k = os.system(build_command_for_tag_notes("PUT", clean_changelog, tag))
    print "\n"

def run_command( bash_command ):
    """Sends command to system.
    """
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    if error is not None :
        print(error)
        print("Terminating...")
        quit()
    return output.strip('\n')

def get_commit_by_tag( tag ):
    return  run_command("git rev-list -n 1 " +  tag)

def parse_raw_changelog(non_formatted_text ) :
    """Parses raw changelog extracted from git.
     Returns map {'issue_type': ['issues_array']}
    """
    mapped_issues = {}
    for line in non_formatted_text.splitlines() :
        #skipping empty lines, non related to issues description lines, etc...
        if line == "" :
            continue
        if line.startswith("See merge request") or line.startswith("This reverts commit"):
            continue
        if len(line)<=11 and not " " in line:
            continue
        categorized_issue = False
        for issue_type in issue_types:
            issue_prefix = issue_type + ": "
            #checking lower cased strings to prevent skipping misnamed issues
            if line.strip(" ").lower().startswith(issue_prefix.lower()) :
                categorized_issue = True
                line = line.replace(issue_prefix, "")
                if issue_type not in mapped_issues :
                    mapped_issues.update({issue_type : [line]})
                else:
                    mapped_issues[issue_type].append(line)
                break
        if categorized_issue :
            continue
        #if code reach that line - means issue type is not in issue_types -> typo or uncategorized issuetype
        if uncategorized_issueType not in mapped_issues :
            mapped_issues.update({uncategorized_issueType : [line]})
        else:
            mapped_issues[uncategorized_issueType].append(line)
        continue      
    return mapped_issues

line_breaker = "\n"
issue_types = {"Enhancement","Fix", "Feature", "Ongoing", "Checkmark",
"Related", "Lab", "Live", "Refactor", "Nochangelog", "Technical"}

uncategorized_issueType = "Uncategorized"

def convert_changelog_text_to_md(non_formatted_text , header ) : 
    """Returns .MD formatted changelog based on raw formatted text.
     Header - 'title' for set of issues in that changelog
    """
    mapped_issues = parse_raw_changelog(non_formatted_text)
    if len(mapped_issues) == 0 :
        return ""
    res = ""
    if not (not header or header == ""):
      res += build_header_project(header) + line_breaker
    res += build_changelog_body(mapped_issues)
    return res

def build_header_project(header )  :
    return "## " + header + line_breaker

def build_header_issue(header )  :
    return "### " + header + ":" + line_breaker

def build_issue(issue ) :
    return " - " + issue

def build_changelog_body(mapped_issues)  :
    res = ""
    for issue_type  in  mapped_issues :
        res += build_header_issue(issue_type)
        for issue in mapped_issues[issue_type] :
            res += build_issue(issue) + line_breaker
        res += line_breaker
    return res

def build_message_to_slack(tag) :
    return os.environ['CI_PROJECT_URL']  + "/tags/" + tag

def send_message_to_slack(text, channel, token, username) :
    """Sends message to slack
        text - text to be send
        channel - channel name at slack. example: #general
        token - bot token for posting messages
        username - bot name
    """
    #http post request to slack service to post message to specific channel
    command = 'curl https://slack.com/api/chat.postMessage -X POST -d "as_user=false" -d "channel='+ channel+'" -d "username='+username+'" -d "token='+token+'" -d "text='+text + '"'
    os.system(command)

def main():
    new_commit = os.environ['CI_COMMIT_SHA']
    old_commit = ""
    if "CI_BUILD_TAG" in os.environ:
        print 'there is a tag'
        new_tag = os.environ["CI_BUILD_TAG"]
        old_commit = get_commit_by_tag(run_command("git describe --abbrev=0 --tags "+ new_tag +"^"))
    else :
        old_commit = get_commit_by_tag(run_command("git describe --abbrev=0 --tags"))

    md_formatted_changelog = get_md_formatted_changelog(new_commit, old_commit)

    print( md_formatted_changelog)
    if "CI_BUILD_TAG" in os.environ:
        put_tag_notes_on_gitlab(md_formatted_changelog, new_tag)
        send_message_to_slack(build_message_to_slack(new_tag), os.environ['ANNOUNCEMENT_CHANNEL'], os.environ['SLACK_BOT_TOKEN'], os.environ['GITLAB_USER_NAME'] )
    
if __name__ == "__main__":
    main()
