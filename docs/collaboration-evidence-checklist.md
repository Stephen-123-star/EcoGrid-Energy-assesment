# EcoGrid Energy - Collaboration Evidence Checklist

## 1. Overview & Academic Integrity

For **ICT711 Assessment 2**, students must provide verifiable visual evidence of authentic team collaboration across three primary platforms:
1. **GitHub** (Version Control & CI/CD)
2. **Monday.com / Jira / Trello** (Agile Task Management)
3. **Team Communication Tool** (Microsoft Teams / Discord / Slack)

> **Important Note:** AI agents cannot and must not fabricate screenshots, user accounts, or project board activity. This checklist specifies the exact visual artifacts your team must capture from your genuine project workspace.

---

## 2. GitHub Evidence Checklist

Capture clear, full-window screenshots showing your repository URL and contributor names:

| # | Artifact | What to Display | Purpose / Rubric Mapping |
| :-: | :--- | :--- | :--- |
| **GH-1** | **Repository Home Page** | Repository title (`EcoGrid-Energy`), README preview, file tree, and recent commit message. | Verifies active project repository. |
| **GH-2** | **Commit History** | `git log` / GitHub Commits tab showing progressive, meaningful commit messages across team members. | Proves incremental development and individual member contributions. |
| **GH-3** | **Contributors & Insights Graph** | GitHub Insights $\rightarrow$ Contributors tab showing commit frequency and lines of code contributed per member. | Verifies authentic multi-author contribution. |
| **GH-4** | **GitHub Actions CI Pipeline** | Actions tab showing successful green checkmark on the `EcoGrid CI Pipeline` workflow. | Demonstrates automated testing and fitness function execution in CI. |
| **GH-5** | **Pull Requests & Code Reviews** | At least one closed Pull Request showing reviewer comments, approvals, and merged branches. | Proves peer code review and collaborative git branching. |

---

## 3. Monday.com (Task Management) Evidence Checklist

Capture screenshots from your team's project board showing task distribution:

| # | Artifact | What to Display | Purpose / Rubric Mapping |
| :-: | :--- | :--- | :--- |
| **MON-1** | **Full Sprint Board** | Columns for: *Item Name*, *Owner / Assignee*, *Status* (Done, In Progress, Review, To Do), *Priority*, and *Due Date*. | Demonstrates Agile sprint planning and workflow management. |
| **MON-2** | **Architectural User Stories** | Tasks representing core features: "Implement SmartMeterSimulator", "Marketplace FIFO Matching", "Financial Settlement Idempotency", "Architectural Fitness Functions". | Shows direct mapping between assessment requirements and team tasks. |
| **MON-3** | **Task Detail & Activity Log** | Open task modal showing comments, status updates, or time-tracking entries between group members. | Demonstrates ongoing task-level coordination. |
| **MON-4** | **Sprint Burndown / Completed View** | Completed tasks grouped under the "Done" milestone with 100% completion status. | Proves delivery against planned sprint commitments. |

---

## 4. Team Communication Evidence Checklist

Capture screenshots from your official communication channel (Teams/Discord/Slack):

| # | Artifact | What to Display | Purpose / Rubric Mapping |
| :-: | :--- | :--- | :--- |
| **COM-1** | **Kickoff & Domain Modeling** | Initial discussion agreeing on Bounded Contexts (`smart_meter`, `marketplace`, `settlement`) and Event-Driven Architecture. | Proves collective architectural decision-making. |
| **COM-2** | **Task Allocation & Pair Programming** | Messages assigning specific modules or ADR documentation to individual team members. | Proves organized labor distribution. |
| **COM-3** | **Triage / Technical Problem-Solving** | Discussion regarding resilience (e.g., how to handle duplicate trades via idempotency or DLQ retry policies). | Demonstrates critical thinking and peer problem-solving. |
| **COM-4** | **Final Verification & Review** | Team message confirming all automated tests passed and reviewing the final demonstration metrics. | Demonstrates collaborative quality assurance. |
