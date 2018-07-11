"""Script parses changelog from git based on 2 latest tags, formates changelog to .md format, creates/updates release on gitlab, posts to slack
"""
import subprocess
import os

def getMdFormattedChangelog(newCommit, oldCommit) : 
    #saving parameters this way to make sure that they are read properly on bash command
    get_log_format = '%x1f'.join(['%b', '%h']) + '%x1e'
    bashCommand = 'git --no-pager --git-dir=.git log --first-parent --format="%s"' % get_log_format   + " "+ newCommit+"..." + oldCommit
    #getting raw changelog from git
    rawChangelog = sendCommand(bashCommand).replace("\"", "")
    return  ConvertChangelogTextToMd(rawChangelog, None)

def buildCommandForTagNotes(reqType, cleanChangeLog, tag) : 
    formattedProjectPath = os.environ['CI_PROJECT_PATH'].replace("/","%2F")  
    return 'curl  -X '+reqType+'  --header "PRIVATE-TOKEN: $GITLAB_API_PRIVATE_TOKEN" -d description="'+cleanChangeLog+ '" https://git.smarpsocial.com/api/v4/projects/"'+ formattedProjectPath+ '"/repository/tags/"'+tag+'"/release'
     
def putTagNotesOnGitlab( cleanChangeLog  , tag):
    # create a release notes just in case it hasnt'been created before
    k = os.system(buildCommandForTagNotes("POST", cleanChangeLog, tag))
    # updating just in case it had been created before
    k = os.system(buildCommandForTagNotes("PUT", cleanChangeLog, tag))
    print "\n"

def sendCommand( bashCommand ):
    """Sends command to system.
    """
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    if error is not None :
        print(error)
        print("Terminating...")
        quit()
    return output.strip('\n')

def getCommitByTag( tag ):
    return  sendCommand("git rev-list -n 1 " +  tag)

def parseRawChangelog(nonFormattedText ) :
    """Parses raw changelog extracted from git.
     Returns map {'issue_type': ['issues_array']}
    """
    mappedIssues = {}
    for line in nonFormattedText.splitlines() :
        #skipping empty lines, non related to issues description lines, etc...
        if line == "" :
            continue
        if line.startswith("See merge request") or line.startswith("This reverts commit"):
            continue
        if len(line)<=11 and not " " in line:
            continue
        categorizedIssue = False
        for issueType in issueTypes:
            issuePrefix = issueType + ": "
            #checking lower cased strings to prevent skipping misnamed issues
            if line.lower().startswith(issuePrefix.lower()) :
                categorizedIssue = True
                line = line.replace(issuePrefix, "")
                if issueType not in mappedIssues :
                    mappedIssues.update({issueType : [line]})
                else:
                    mappedIssues[issueType].append(line)
                break
        if categorizedIssue :
            continue
        #if code reach that line - means issue type is not in issueTypes -> typo or uncategorized issuetype
        if uncategorizedIssueType not in mappedIssues :
            mappedIssues.update({uncategorizedIssueType : [line]})
        else:
            mappedIssues[uncategorizedIssueType].append(line)
        continue      
    return mappedIssues

lineBreaker = "\n"
notEnoughInputParametersErr = "Not enough input parameters"
issueTypes = {"Enhancement","Fix", "Feature", "Ongoing", "Checkmark",
"Related", "Lab", "Live", "Refactor", "Nochangelog", "Technical"}

uncategorizedIssueType = "Uncategorized"

def ConvertChangelogTextToMd(nonFormattedText , header ) : 
    """Returns .MD formatted changelog based on raw formatted text.
     Header - 'title' for set of issues in that changelog
    """
    mappedIssues = parseRawChangelog(nonFormattedText)
    if len(mappedIssues) == 0 :
        return ""
    res = ""
    if not (not header or header == ""):
      res += buildHeaderProject(header) + lineBreaker
    res += buildChangelogBody(mappedIssues)
    return res

def buildHeaderProject(header )  :
	return "## " + header + lineBreaker

def buildHeaderIssue(header )  :
	return "### " + header + ":" + lineBreaker

def buildIssue(issue ) :
	return " - " + issue

def buildChangelogBody(mappedIssues)  :
	res = ""
	for issueType  in  mappedIssues :
		res += buildHeaderIssue(issueType)
		for issue in mappedIssues[issueType] :
			res += buildIssue(issue) + lineBreaker
		res += lineBreaker
	return res

def buildMessageToSlack(tag) :
    return os.environ['CI_PROJECT_URL']  + "/tags/" + tag

def sendMessageToSlack(text, channel, token, username) :
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
    newCommit = os.environ['CI_COMMIT_SHA']
    oldCommit = ""
    if "CI_BUILD_TAG" in os.environ:
        newTag = os.environ["CI_BUILD_TAG"]
        oldCommit = getCommitByTag(sendCommand("git describe --abbrev=0 --tags "+ newTag +"^"))
    else :
        oldCommit = getCommitByTag(sendCommand("git describe --abbrev=0 --tags"))

    mdFormattedChangelog = getMdFormattedChangelog(newCommit, oldCommit)

    print( mdFormattedChangelog)

    if "CI_BUILD_TAG" in os.environ:
        putTagNotesOnGitlab(mdFormattedChangelog, newTag)
        sendMessageToSlack(buildMessageToSlack(newTag), os.environ['ANNOUNCEMENT_CHANNEL'], os.environ['SLACK_BOT_TOKEN'], os.environ['GITLAB_USER_NAME'] )
    
if __name__ == "__main__":
    main()
