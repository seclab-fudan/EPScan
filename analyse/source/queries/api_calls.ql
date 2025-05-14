/**
 * api_calls.ql -- 查询所有 K8s API 调用点
 *
 * Copyright (C) 2024 KAAAsS
 */
import go
import k8sapi.General
import analyse.Function

from
    K8sApiCall apiCall
select
    // Name, API Type, Callsite Parent, Resource Type, Verb, Callsite Loc
    apiCall,
    apiCall.getApiType(),
    getParentFunction(apiCall.getCall()).getQualifiedName(),
    apiCall.getResourceName(),
    apiCall.getVerbName(),
    apiCall.getLocation().toString()
