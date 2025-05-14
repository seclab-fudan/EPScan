# EPScan
"EPScan: Automated Detection of Excessive RBAC Permissions in Kubernetes Applications"

## Get started (WIP)

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

## Publication

If you find this project useful for your research, please consider citing our paper:

**EPScan: Automated Detection of Excessive RBAC Permissions in Kubernetes Applications**

*Yue Gu, Xin Tan, Yuan Zhang, Siyan Gao, Min Yang*

In *IEEE Symposium on Security and Privacy (SP)*, 2025.

DOI: [10.1109/SP61157.2025.00011](https://doi.ieeecomputersociety.org/10.1109/SP61157.2025.00011)

```bibtex
@inproceedings{gu2024epscan,
  title={EPScan: Automated Detection of Excessive RBAC Permissions in Kubernetes Applications},
  author={Gu, Yue and Tan, Xin and Zhang, Yuan and Gao, Siyan and Yang, Min},
  booktitle={2025 IEEE Symposium on Security and Privacy (SP)},
  pages={11--11},
  year={2024},
  organization={IEEE Computer Society}
}
```

## TODOs

- [ ] Documentation
- [ ] Translation
