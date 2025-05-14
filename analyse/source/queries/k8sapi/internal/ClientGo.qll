/**
 * Client-go API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import go

module ClientGo {

  class ApiPackage extends Package {
    ApiPackage() { this.getPath().regexpMatch("^k8s\\.io/client-go/kubernetes/typed/\\w+/\\w+$") }

    string getApiGroup() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/kubernetes/typed/(\\w+)/\\w+$", 1)
    }

    string getApiVersion() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/kubernetes/typed/\\w+/(\\w+)$", 1)
    }

    string getShortName() { result = this.getApiGroup() + "/" + this.getApiVersion() }
  }

  class ResourceInterfaceGetter extends Type {
    ApiPackage package;

    ResourceInterfaceGetter() {
      this.getPackage() = package and
      this.getName().regexpMatch("^\\w+Getter$")
    }

    ApiPackage getApiPackage() { result = package }

    string getResourceName() {
      result = this.getName().regexpCapture("^(\\w+)Getter$", 1).toLowerCase()
    }
  }

  class ResourceInterface extends Type {
    ResourceInterfaceGetter getter;

    ResourceInterface() { this = getter.getMethod(_).getResultType(0) }

    string getResourceName() { result = getter.getResourceName() }

    string getPkgVersionName() {
      result = getter.getApiPackage().getShortName() + "." + this.getName()
    }
  }

  class ResourceMethod extends Method {
    ResourceInterface resource;

    ResourceMethod() { this.getReceiverType() = resource }

    ResourceInterface getResourceInterface() { result = resource }

    string getResourceName() {
      result = resource.getResourceName()
    }

    string getVerbName() { result = methodToVerb(this.getName()) }

    bindingset[method]
    private string methodToVerb(string method) {
      method = "Create" and result = "create"
      or
      method = "Update" and result = "update"
      or
      method = "Delete" and result = "delete"
      or
      method = "DeleteCollection" and result = "deletecollection"
      or
      method = "Get" and result = "get"
      or
      method = "List" and result = "list"
      or
      method = "Watch" and result = "watch"
      or
      method = "Patch" and result = "patch"
      or
      method = "Apply" and result = "patch"
      or
      not method.regexpMatch("^(Create|Update|Delete|DeleteCollection|Get|List|Watch|Patch|Apply)$") and
      result = "unknown:" + method
    }

    override string toString() {
      result = "<" + resource.getPkgVersionName() + "." + this.getName() + ">"
    }
  }

  class ApiCall extends CallExpr {
    ResourceMethod method;

    ApiCall() { this.getTarget() = method }

    ResourceMethod getResourceMethod() { result = method }

    string getVerbName() { result = method.getVerbName() }

    string getResourceName() { result = method.getResourceName() }

    override string toString() { result = "Call " + method.toString() }
  }
}
