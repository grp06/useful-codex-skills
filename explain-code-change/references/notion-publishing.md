# Notion publishing

Use the Notion workspace authenticated by the current user. Never embed a workspace ID, parent ID, access token, email address, or personal destination in this skill.

## Preflight

1. Confirm that Notion read and write tools are available.
2. If they are unavailable, preserve the completed Markdown draft, tell the user to connect and authenticate the Notion integration, and do not claim that the page was published.
3. When supported, fetch `self` to identify the connected workspace and user. If the user names a different workspace, stop before writing and ask them to switch the connection.
4. Read `notion://docs/enhanced-markdown-spec` through the MCP resource interface before composing content. Do not guess toggle, callout, table, diagram, or code-block syntax.

## Resolve the destination

Honor an explicit Notion page, database, data source, or workspace destination from the user.

- For a parent page, fetch it first and use its page ID.
- For a database, fetch it first, select the correct data source, and use the returned data-source ID and actual title-property name.
- If the user supplies no destination and the connector supports standalone private pages, omit `parent` to create a private workspace-level page.
- If the connector requires a parent, ask the user for a writable destination. Never infer one from the repository, topic, audience, search results, or related team resources.
- Do not write to a different destination merely because the requested destination is inaccessible.

When updating an existing page, preserve its location unless the user explicitly requests a move.

## Privacy contract

Treat new pages as private by default unless the user explicitly names a shared destination or asks to share or publish the page.

Resolve placement before creation whenever possible. If a newly created page lands in an unintended shared location, move only the page created during the current run and only when the connector supports a workspace-level private destination. Fetch it again after moving. Otherwise, report the placement problem clearly instead of assuming privacy.

Do not report a page as private until its fetched metadata or ancestor path verifies that it has no shared page, database, or data-source ancestor. If the connector cannot expose placement, say that privacy could not be verified.

## Create and verify

For a standalone page, set the `title` property and keep the title out of the body content. For a database page, use the fetched schema rather than assuming a property named `title`.

After creation:

1. Fetch the returned page URL or ID.
2. Verify the title and expected section headings.
3. Inspect rendered tables, toggles, callouts, code blocks, diagrams, links, and numbering.
4. Confirm that exactly five quiz questions and five answer toggles are present.
5. Verify the requested parent or private workspace placement.
6. Correct rendering defects before reporting the page as complete.

Return the verified page link and state any limits in content, execution, or privacy verification.
