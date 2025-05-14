/**
 * all_sdk_calls.ql -- 查询所有调用过的 SDK 函数
 *
 * Copyright (C) 2024 KAAAsS
 */
import go

predicate isPublicFunction(Function f) {
    f.getName().regexpMatch("^[A-Z].*")
}

predicate isSdkFunction(Function f) {
    f.getPackage().getPath().matches("sigs.k8s.io/controller-runtime/pkg/client%")
        or
    f.getPackage().getPath().matches("sigs.k8s.io/controller-runtime/pkg/controller/controllerutil%")
        or
    f.getPackage().getPath().matches("k8s.io/client-go/dynamic%")
        or
    f.getPackage().getPath().matches("k8s.io/client-go/kubernetes%")
        or
    f.getPackage().getPath().matches("k8s.io/client-go/tools/cache%")
}

from
    CallExpr call,
    Function f
where
    call.getTarget() = f
    and isPublicFunction(f)
    and isSdkFunction(f)
select
    // full_name, package, name
    f.getQualifiedName(),
    f.getPackage().getPath(),
    f.getName()
