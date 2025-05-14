/**
 * ClientGo Type-3 API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import go

module ClientGoType3 {
  import Common::K8sApiType

  class ApiFunction extends Function {
    ApiFunction() {
      this.hasQualifiedName("k8s.io/client-go/tools/cache",
        ["NewFilteredListWatchFromClient", "NewGenericLister", "NewListWatchFromClient"])
      or
      this.hasQualifiedName("k8s.io/client-go/dynamic/dynamicinformer",
        ["NewFilteredDynamicInformer", "ForResource"])
    }

    int getResourceArgIndex() { result = methodToArgIndex(this.getName()) }

    string getVerbName() { result = methodToVerb(this.getName()) }

    bindingset[method]
    private string methodToVerb(string method) {
      method = "NewFilteredListWatchFromClient" and result = "list"
      or
      method = "NewFilteredListWatchFromClient" and result = "watch"
      or
      method = "NewGenericLister" and result = "list"
      or
      method = "NewGenericLister" and result = "get"
      or
      method = "NewListWatchFromClient" and result = "list"
      or
      method = "NewListWatchFromClient" and result = "watch"
      or
      method = "NewFilteredDynamicInformer" and result = "list"
      or
      method = "NewFilteredDynamicInformer" and result = "watch"
      or
      method = "ForResource" and result = "list"
      or
      method = "ForResource" and result = "watch"
    }

    bindingset[method]
    private int methodToArgIndex(string method) {
      method = "NewFilteredListWatchFromClient" and result = 1  // string
      or
      method = "NewGenericLister" and result = 1 // schema.GroupResource
      or
      method = "NewListWatchFromClient" and result = 1 // string
      or
      method = "NewFilteredDynamicInformer" and result = 1 // schema.GroupVersionResource
      or
      method = "ForResource" and result = 0 // schema.GroupVersionResource
    }
  }

  class CandidateApiCall extends CallExpr {
    ApiFunction method;

    CandidateApiCall() { this.getTarget() = method }

    string getVerbName() { result = method.getVerbName() }

    string getTypeHint() {
      result =
      this.getResourceArg().getType().pp() + " @ " +
          this.getResourceArg().toString()
    }

    Expr getResourceArg() { result = this.getArgument(method.getResourceArgIndex()) }
  }

  class ApiCall extends CandidateApiCall {
    string resourceName;

    ApiCall() { exprPointsToResourceConst(this.getResourceArg(), resourceName) }

    string getResourceName() { result = resourceName }

    override string toString() {
      result = "Call <" + method.getName() + ">"
    }
  }
}
