"""Each tool's guide, Decision 0026 G1 and PRD-Tool-Catalog TG-01: what it does, when to use it,
and why it's useful. They describe and never grant, and hold no value or secret. A unit test fails
for a registered or planned tool without one.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolGuide:
    what: str
    when: str
    why: str


TOOL_GUIDES: dict[str, ToolGuide] = {
    # Planning
    "propose_plan": ToolGuide(
        "Proposes the plan for a goal as tasks tied to its success criteria, or revises it with a "
        "reason.",
        "At the start of every goal, and again when the work shows the plan was wrong.",
        "A run's progress, verification and budget are all measured against this plan.",
    ),
    "complete_task": ToolGuide(
        "Marks one plan task done, citing saved files or tool effects as its evidence.",
        "When a task's work is finished and there is something real to point to.",
        "Completion is checked against evidence, so a run can't claim work it didn't do.",
    ),
    "workflow_approval": ToolGuide(
        "Holds a workflow at an explicit approval step until a person decides.",
        "Only inside a workflow, where its author placed an approval gate.",
        "Some steps should never continue without a person looking first.",
    ),
    # General
    "calculate": ToolGuide(
        "Computes the sum, mean, minimum or maximum of a list of numbers.",
        "Whenever an answer depends on arithmetic over figures the run already has.",
        "Exact arithmetic instead of a model's estimate.",
    ),
    "search_memory": ToolGuide(
        "Searches this workspace's memory and saved evidence by keyword.",
        "Before researching something the workspace may already know.",
        "It reuses earlier work and keeps answers consistent across runs.",
    ),
    "read_offload": ToolGuide(
        "Reads back a long tool result kept outside the conversation, a page at a time.",
        "When a tool's output was stored as a pointer because it was too long to show.",
        "Long results stay available without filling the model's context.",
    ),
    # Web search
    "search_web": ToolGuide(
        "Searches the web through Jina in pages of 10, up to 30 ranked results a call, and returns "
        "titles, links and snippets without repeats.",
        "To find sources on a topic the run can't answer from its own files.",
        "Fresh public information, labelled as third-party data and not instructions.",
    ),
    "google_search": ToolGuide(
        "Searches Google through SerpApi in pages of 10, up to 30 ranked results a call, and "
        "returns titles, links and snippets without repeats.",
        "When a run needs what Google ranks for a query, such as official pages or recent news.",
        "Google's own ranking, labelled as third-party data and not instructions.",
    ),
    "google_map": ToolGuide(
        "Lists the pages Google has indexed for a site or one of its sections, up to 30.",
        "Before reading a site, to see which of its pages Google knows about.",
        "It finds a site's pages through Google without walking the site.",
    ),
    "google_extract": ToolGuide(
        "Reads up to five web pages as markdown, directly from their sites, obeying robots.txt.",
        "When pages found with Google need to be read, not just their snippets.",
        "Page text without a third-party reader, labelled as data and not instructions.",
    ),
    "google_crawl": ToolGuide(
        "Maps a site with Google, then reads up to ten of its pages as markdown.",
        "When an answer is spread across several pages of one site.",
        "A site's pages found and read in one call, politely and within fixed limits.",
    ),
    "tavily_search": ToolGuide(
        "Searches the web through Tavily for up to 20 ranked results, with optional domains, topic "
        "and time range.",
        "To find recent or focused sources, such as news from the last week or one site's pages.",
        "Search tuned for research, with results scored by relevance.",
    ),
    # Website extraction
    "extract_website_content": ToolGuide(
        "Reads one web page as markdown, with its links, through Jina's reader.",
        "When a specific page's content is needed, not just its search snippet.",
        "Clean page text for reading or citing, cut to a safe size.",
    ),
    "tavily_extract": ToolGuide(
        "Reads up to five web pages as markdown through Tavily.",
        "When several known pages need to be read together.",
        "Several pages' content in one call, each labelled third-party.",
    ),
    # Web crawling
    "tavily_map": ToolGuide(
        "Lists a site's pages within fixed depth, breadth and count limits.",
        "Before reading a site, to see which of its pages exist.",
        "It finds the right pages without reading the whole site.",
    ),
    "tavily_crawl": ToolGuide(
        "Reads a site's pages as markdown within fixed depth, breadth and count limits.",
        "When an answer is spread across several pages of one site.",
        "A bounded read of a site, which can't wander off it.",
    ),
    # Files
    "read_run_file": ToolGuide(
        "Reads a file of this run, optionally a range of its lines.",
        "To use an attached document or a file the run saved earlier.",
        "The run works from its real inputs, read exactly.",
    ),
    "read_csv": ToolGuide(
        "Reads a CSV file of this run as typed columns and bounded rows.",
        "When a spreadsheet-like input needs counting, filtering or summarizing.",
        "Structured data instead of raw text, with types inferred.",
    ),
    "save_artifact": ToolGuide(
        "Saves a file for this run as a new version.",
        "Whenever the run produces something worth keeping, such as a report or a draft.",
        "Work is kept, versioned and citable as evidence.",
    ),
    "publish_artifact": ToolGuide(
        "Publishes a saved file of this run as a verified private artifact.",
        "When a saved file is the run's deliverable.",
        "Verification requires a published file, and the owner can open it later.",
    ),
    "read_artifact": ToolGuide(
        "Reads a published text artifact of this workspace by its ID, optionally a range of lines.",
        "When a workflow step builds on an earlier step's published work, named by artifact IDs.",
        "Each step reads the exact files the previous one published, checked against their hash.",
    ),
    "store_remote_file": ToolGuide(
        "Downloads a public text file of up to 1 MiB and saves it under outputs/.",
        "When a dataset or document at a known https URL is needed as a file.",
        "The run keeps an exact copy to read, with the source URL guarded.",
    ),
    # Market data
    "market_history": ToolGuide(
        "Gets daily or weekly prices for up to five Yahoo Finance symbols.",
        "For questions about price moves, exchange rates such as CRC=X, or crypto prices.",
        "Real closing prices to compare or compute with.",
    ),
    "inflation_rates": ToolGuide(
        "Gets annual consumer price inflation for Costa Rica, the USA and the euro area.",
        "When a note or comparison needs inflation over recent years.",
        "Official World Bank figures, with their source named.",
    ),
    # Browsing
    "browse_goal": ToolGuide(
        "Reads websites in an isolated browser to pursue a task, within the domains it is given.",
        "When an answer needs following links across pages, which search and extract can't do.",
        # Decision 0035 Y2, Y3, Y5, Y10, Y12 and Y13.
        "Each call waits for approval while YOLO is off, and then only reads. While it is on, a "
        "call goes only to its Expert's browse domains, may press, type and submit there, stops "
        "at a bot check, and may name an output schema for a typed result. An Expert browsing a "
        "wiki or forum says in its instructions never to edit or post.",
    ),
    # Code
    "search_files": ToolGuide(
        "Searches this run's files by regular expression, with context lines.",
        "To find where something is defined or mentioned across the run's files.",
        "Precise search without a terminal.",
    ),
    "read_code_file": ToolGuide(
        "Reads a file of this run as numbered lines, with paging.",
        "Before editing code, to see exactly what is there.",
        "Line numbers make later edits exact.",
    ),
    "write_code_file": ToolGuide(
        "Writes a file under outputs/ as a new version.",
        "When creating a new file or replacing one entirely.",
        "Every write is a version, so nothing is lost.",
    ),
    "patch_code_file": ToolGuide(
        "Replaces an exact string in a file under outputs/, once or everywhere.",
        "For a small, precise change to a file the run already has.",
        "It changes only what's named, or nothing if the match is ambiguous.",
    ),
    # Connectors
    "create_github_issue": ToolGuide(
        "Creates an issue, with optional labels, in the workspace's GitHub repository.",
        "When the run finds something that should be tracked, such as a bug or a task.",
        "Work leaves the run as a real issue, and only after a person approves it.",
    ),
    "github_list_pull_requests": ToolGuide(
        "Lists pull requests in the configured repository by state, base and date.",
        "For release notes, reviews or a summary of recent changes.",
        "An exact view of the repository's work, read-only.",
    ),
    "github_list_workflow_runs": ToolGuide(
        "Lists GitHub Actions runs, with each failed run's failing jobs.",
        "When triaging failing builds or tests.",
        "It shows what broke and where, read-only.",
    ),
    "github_search_issues": ToolGuide(
        "Searches issues in the configured repository by text and state.",
        "Before filing an issue, or to find earlier reports of a problem.",
        "It avoids duplicates and links related work.",
    ),
    "github_read_file": ToolGuide(
        "Reads a text file from the configured repository at a branch, tag or commit.",
        "When the run needs code or docs from the repository.",
        "The source at an exact revision, without cloning.",
    ),
    "github_open_pull_request": ToolGuide(
        "Proposes a pull request with up to 20 files' new content.",
        "When the run has a concrete change for the repository.",
        "A person reviews each file's diff and approves before anything is pushed.",
    ),
    # Delegation
    "assign_specialist": ToolGuide(
        "Gives a bounded task to an Expert in this session and waits for its result.",
        "When part of a goal needs another Expert's tools or instructions.",
        "Work is split cleanly, within the same budget and approvals.",
    ),
    # Learning
    "propose_improvement": ToolGuide(
        "Proposes a memory or skill change for a person to review.",
        "When a run learns something future runs should reuse.",
        "The workspace improves over time, but only with a person's approval.",
    ),
    # Automation
    "cronjob": ToolGuide(
        "Lists, creates, updates, pauses, resumes, runs now or removes this workspace's routines.",
        "When work should repeat on a schedule, or a schedule needs changing or running at once.",
        "Recurring goals and workflows run by themselves, and every change waits for a person.",
    ),
}
