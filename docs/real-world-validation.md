# Real-World Validation Loop

LaunchKit needs feedback from repositories it was not designed against.

## Validate Against An External Repo

```bash
bash scripts/validate_external_repo.sh /absolute/path/to/repo
```

The script copies the target repo into a temporary workspace, runs `launchkit init`, runs `launchkit generate`, and prints the generated file list. It avoids mutating the original repository.

## What To Capture

When LaunchKit gets something wrong, collect these artifacts:

1. the target repo structure at a high level
2. the generated `launchkit.yaml`
3. the command output from `launchkit init` and `launchkit generate`
4. what LaunchKit inferred incorrectly
5. what the expected output should have been

## Reporting

Open an issue with the real-world validation issue template in `.github/ISSUE_TEMPLATE/real-world-validation.yml`.

That is the fastest path from first-contact feedback to detector and generator improvements.