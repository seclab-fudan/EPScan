/**
 * candidate_api_calls.ql -- 查询所有候选 K8s API 调用点
 *
 * 目前，候选调用点只查询所有可能因为数据流分析失败的 API，所以结果要和 api_calls 合并。
 *
 * Copyright (C) 2024 KAAAsS
 */
import go
import k8sapi.Candidate
import analyse.Function

from
    CandidateApiCall apiCall
select
    // Name, API Type, Callsite Parent, Resource Type Hint, Verb, Callsite Loc
    apiCall,
    apiCall.getApiType(),
    getParentFunction(apiCall.getCall()).getQualifiedName(),
    apiCall.getTypeHint(),
    apiCall.getVerbName(),
    apiCall.getLocation().toString()
