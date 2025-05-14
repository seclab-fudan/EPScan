import json
from pathlib import Path
from pprint import pprint

import typer

from analyse.k8s.basic import ObjectStore
from modules.config_analyse import PodPermAnalyser
from modules.perm_compare import PermComparer
from modules.pod_source_match import PodSourceMatcher
from modules.source_analyse import ApiCallScanner
from modules.storage import ProjectFolder
from utils.log import log_funcs, log_ctx, inject_global_timer, log_elapse

debug, info, warn, error, fatal = log_funcs(from_file=__file__)

app = typer.Typer(
    name="ep-scan",
    help="批量扫描 Kubernetes 项目中的过度权限"
)


@app.command()
def run(
        project_root: Path = typer.Argument(..., exists=True, help="扫描的目标路径"),
        project_name: str = typer.Argument(None, help="指定扫描的项目名称"),
):
    proj = ProjectFolder(project_root)

    for proj_name in proj.projects():
        if project_name and project_name != proj_name:
            continue
        try:
            run_single(proj, proj_name)
        except Exception as e:
            error(f"error in project", project=proj_name, exc_info=e)


def run_single(proj: ProjectFolder, proj_name: str):
    with log_ctx(project=proj_name):
        with log_elapse("scanning project"):
            # 加载配置
            conf_path = proj.conf(proj_name)
            assert conf_path.exists(), f"Config not found in {conf_path}"
            store = ObjectStore.from_config_dir(conf_path)

            if not proj.source(proj_name, None).exists():
                error("source code not found")
                return

            # 1. 源代码分析
            with log_elapse("source code analysis"):
                acs = ApiCallScanner(proj)
                with log_elapse("build db"):
                    acs.build_db(proj_name)
                with log_elapse("scan callsites"):
                    css = acs.scan(proj_name)

            # 2. 源代码-Pod 关联分析
            with log_elapse("pod source matching"):
                psm = PodSourceMatcher(proj, proj_name, store)
                psm.extract_info()
                psm.remove_exception()
                psm.do_match()
                pod_source_result = proj.cache(proj_name, 'pod_source_result.csv')
                psm.save_csv(pod_source_result)
                rt_results = psm.match_callsites(css)

            # 3. 配置分析
            with log_elapse("config analysis"):
                ppa = PodPermAnalyser()
                lf_results = ppa.analyse(store)

            # 4. 权限比较
            with log_elapse("permission compare"):
                pc = PermComparer(lf_results, rt_results)

        # 保存 issues
        issues = pc.scan_ep()
        pprint(issues)
        json_path = proj.result(proj_name, 'issues.json')
        with json_path.open('w') as f:
            json.dump([issue.to_dict() for issue in issues], f, indent=2)


if __name__ == '__main__':
    inject_global_timer()
    app()
