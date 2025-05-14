/**
 * controller-runtime API 调用点的识别
 * 
 * Copyright (C) 2024 KAAAsS
 */

import go

module ControllerRuntime {
  import Common::K8sApiType

  class ClientApi extends Function {
    ClientApi() {
      this.hasQualifiedName("sigs.k8s.io/controller-runtime/pkg/client.Client",
        ["Get", "List", "Create", "Update", "Delete", "Patch", "DeleteAllOf"])
        or
      this.hasQualifiedName("sigs.k8s.io/controller-runtime/pkg/client.WithWatch", "Watch")
        or
      this.hasQualifiedName("sigs.k8s.io/controller-runtime/pkg/controller/controllerutil",
        ["CreateOrPatch", "CreateOrUpdate"])
    }

    int getResourceArgIndex() { result = methodToArgIndex(this.getName()) }

    string getVerbName() { result = methodToVerb(this.getName()) }

    bindingset[method]
    private string methodToVerb(string method) {
      method = "Get" and result = "get"
      or
      method = "List" and result = "list"
      or
      method = "Create" and result = "create"
      or
      method = "Update" and result = "update"
      or
      method = "Delete" and result = "delete"
      or
      method = "Patch" and result = "patch"
      or
      method = "DeleteAllOf" and result = "deletecollection"
      or
      method = "Watch" and result = "watch"
      or
      method = "CreateOrPatch" and result = "create"
      or
      method = "CreateOrPatch" and result = "patch"
      or
      method = "CreateOrUpdate" and result = "create"
      or
      method = "CreateOrUpdate" and result = "update"
    }

    bindingset[method]
    private int methodToArgIndex(string method) {
      method = "Get" and result = 2
      or
      method = "List" and result = 1
      or
      method = "Create" and result = 1
      or
      method = "Update" and result = 1
      or
      method = "Delete" and result = 1
      or
      method = "Patch" and result = 1
      or
      method = "DeleteAllOf" and result = 1
      or
      method = "Watch" and result = 1
      or
      method = "CreateOrPatch" and result = 2
      or
      method = "CreateOrUpdate" and result = 2
    }
  }

  class CandidateApiCall extends CallExpr {
    ClientApi method;

    CandidateApiCall() { this.getTarget() = method }

    string getVerbName() { result = method.getVerbName() }

    string getTypeHint() {
      result = this.getResourceArg().getType().getPackage().toString() + " @ " + this.getResourceArg().getType().pp()
    }

    Expr getResourceArg() { result = this.getArgument(method.getResourceArgIndex()) }
  }

  class ApiCall extends CandidateApiCall {
    ResourceType resource;

    ApiCall() { exprPointsToResource(this.getResourceArg(), resource) }

    string getResourceName() { result = resource.getResourceName() }

    override string toString() {
      result = "Call <" + resource.getPkgVersionName() + "." + method.getName() + ">"
    }
  }
}
