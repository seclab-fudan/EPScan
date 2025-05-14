# EPScan
"EPScan: Automated Detection of Excessive RBAC Permissions in Kubernetes Applications"

# Get started (WIP)

1. Install [uv](https://github.com/astral-sh/uv)
2. Prepare environment
   ```bash
   echo "{YOUR_OPENAPI_KEY}" > openai.key
   ```
3. Prepare project folder
   ```bash
   mkdir project
   mkdir project/app1
   # Put app config to `project/app1/conf`
   # Clone app repo to `project/app1/source/{repo_name}`
   ```
4. Run EPScan
   ```bash
   uv run ep_scan.py ./project
   ```

# TODOs

- [ ] Documentation
- [ ] Translation
