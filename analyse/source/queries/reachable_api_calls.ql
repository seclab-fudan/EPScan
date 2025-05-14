/**
 * reachable_api_calls.ql -- 查询可达的 K8s API 调用点
 *
 * Copyright (C) 2024 KAAAsS
 */
import go
import analyse.RefGraph
import analyse.Function
import k8sapi.General

predicate edges(RefGraph::PathNode pred, RefGraph::PathNode succ) {
    RefGraph::edges(pred, succ)
}

from
    RefGraph::PathNode start,
    RefGraph::PathNode end,
    EntryFunction entryPoint,
    K8sApiCall apiCall
where
    edges+(start, end)
    and start.asFunction() = entryPoint
    and end.asFunction() = getParentFunction(apiCall.getCall())
select
    // Entrypoint, Callsite Parent, Resource Type, Verb, Callsite Loc
    entryPoint.getDeclaration().getLocation().getFile(),
    end.asFunction().getQualifiedName(),
    apiCall.getResourceName(),
    apiCall.getVerbName(),
    apiCall.getLocation().toString()
