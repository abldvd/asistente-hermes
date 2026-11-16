# Changelog

## 2.1.325

- Fixed a security issue in how zstd-compressed responses are decoded
- Added a spinner tip in VS Code and similar integrated terminals about re-running a notebook cell, shown once Claude has read or edited a Jupyter notebook
- Added a line under the error shown when your organization's policy blocks a request, saying how to continue: run `/rewind` and change the message, or run `/clear`
- Added a note for Claude when a sandboxed `git checkout`, `git stash` or autostash pull cannot update protected files such as those in `.claude`
- Fixed `/security-review` and skills' inline git commands stopping with an error in worktrees of bare repositories, `--separate-git-dir` checkouts and Android `repo` checkouts
- Fixed subagents with their own model being moved to the plan-mode model when the model setting is `opusplan` or `haiku`
- Fixed subagents on a different model sizing file reads and MCP results with the main session's model
- Fixed sessions on many third-party gateways and Foundry stopping with a context length error on every turn instead of compacting
- Fixed recent turns sometimes going missing from a resumed session after Claude Code stopped without a clean exit
- Fixed shell commands running in the launch directory after the working directory was deleted; the command now fails with a message and can be re-issued
- Fixed an approved plan edit being lost when the `plansDirectory` folder can't take it: the plan is now saved in the default plans folder, and a warning says where and why
- Fixed a saved `sonnet[1m]` model setting being rewritten on a new install to a model id the API rejects
- Fixed focus view hiding the reply to your prompt when a scheduled task replied after it
- Fixed the prompt sometimes missing from a background subagent's view when fullscreen is off
- Fixed long options in lists and permission prompts being partly overwritten when they wrap, and first-run screens losing lines on narrow terminals
- Fixed startup warnings about permission rules and the "N MCP servers need authentication" notice being recorded as seen when they were scrolled out of view
- Fixed the welcome header showing control characters or splitting across lines when an agent's name or the working folder contains them or a line break
- Fixed the red error shown when Claude tries a command only you can run: a dim line now says it runs only when you type it at the prompt
- Fixed `/stats` showing an Active days total that was one day too high
- Fixed `/insights` saying a report was ready when no session qualified for analysis, and writing two values into its HTML report without escaping them
- Fixed `/voice` saying voice mode changed when managed settings, `--settings`, or the project's `.claude/settings.json` or `.claude/settings.local.json` kept it as it was; it now says what holds it
- Fixed the IDE welcome dialog showing Cmd+Esc for Quick Launch on Windows and Linux
- Fixed Slack app tips showing when your organization's policy denies cloud sessions
- Fixed `claude purge` hanging silently when there is no terminal to read keys from, and its project picker and `-i` prompts ignoring the keyboard when stdin is piped
- Fixed `claude plugin eval --output-dir ''` writing the report into the current folder; it now exits with an error
- Fixed `claude -p` text output on a terminal passing control sequences other than text styling; pipes and files are unchanged
- Fixed leftover `.oauth_refresh.lock.owner.tmp.*` files piling up in the config directory
- Fixed `/fast` saying "Fast mode has been disabled by your organization" under the keyless Console sign-in, where Claude Code had not asked the server
- Fixed `/model` saying that your organization restricts a model when Claude Code could not check that, for example with no network
- Fixed "Sign in with your Console account" in `/login` replacing your existing login when you pressed Esc right after the browser step
- Fixed the browser showing the sign-in success page in some cases where sign-in failed or was canceled
- Fixed `claude auth status` and other short commands leaving a lock behind on a Console profile, which made the next session hang for about a minute
- Fixed background sessions started on your claude.ai login using (and billing) an API key or token from the shell that started the background service
- Fixed more cases of a session moving to another sign-in in the background; these moves are now refused, with a message saying what works
- Fixed a second Enter in the exit dialog stopping background work after the move to the background was refused
- Fixed token counting on Amazon Bedrock sending the conversation to Bedrock when the `allowedProviders` managed setting does not allow it
