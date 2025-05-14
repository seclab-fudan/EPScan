/**
 * Client-go Informer API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import go

module ClientGoInformer {
  class ApiPackage extends Package {
    ApiPackage() { this.getPath().regexpMatch("^k8s\\.io/client-go/informers/\\w+/\\w+$") }

    string getApiGroup() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/informers/(\\w+)/\\w+$", 1)
    }

    string getApiVersion() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/informers/\\w+/(\\w+)$", 1)
    }

    string getShortName() { result = this.getApiGroup() + "/" + this.getApiVersion() }
  }

  class ResourceInterface extends Type {
    ApiPackage package;

    ResourceInterface() {
      this.getPackage() = package and
      this.getName().regexpMatch("^[A-Z]\\w+Informer$")
    }

    string getResourceName() { result = this.getName().regexpCapture("^(\\w+)Informer$", 1).toLowerCase() }

    string getPkgVersionName() {
      result = package.getShortName() + "." + this.getName()
    }
  }

  class ResourceMethod extends Method {
    ResourceInterface resource;

    ResourceMethod() {
      this.getReceiverType() = resource
        and
      (this.getName() = "Informer" or this.getName() = "Lister")
    }

    ResourceInterface getResourceInterface() { result = resource }

    string getResourceName() {
      result = resource.getResourceName()
    }

    string getVerbName() { result = methodToVerb(this.getName()) }

    bindingset[method]
    private string methodToVerb(string method) {
      method = "Informer" and result = "list"
      or
      method = "Informer" and result = "watch"
      or
      method = "Lister" and result = "list"
      or
      method = "Lister" and result = "get"
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
