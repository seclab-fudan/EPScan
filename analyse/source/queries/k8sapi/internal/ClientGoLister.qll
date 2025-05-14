/**
 * Client-go Lister API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import go

module ClientGoLister {
  class ApiPackage extends Package {
    ApiPackage() { this.getPath().regexpMatch("^k8s\\.io/client-go/listers/\\w+/\\w+$") }

    string getApiGroup() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/listers/(\\w+)/\\w+$", 1)
    }

    string getApiVersion() {
      result = this.getPath().regexpCapture("^k8s\\.io/client-go/listers/\\w+/(\\w+)$", 1)
    }

    string getShortName() { result = this.getApiGroup() + "/" + this.getApiVersion() }
  }

  class ResourceInterfaceLister extends Function {
    ApiPackage package;

    ResourceInterfaceLister() {
      this.getPackage() = package and
      this.getName().regexpMatch("^New\\w+Lister$")
    }

    ApiPackage getApiPackage() { result = package }

    string getResourceName() {
      result = this.getName().regexpCapture("^New(\\w+)Lister$", 1).toLowerCase()
    }
  }

  class ResourceInterface extends Type {
    ResourceInterfaceLister lister;

    ResourceInterface() { this = lister.getResultType(0) }

    string getResourceName() { result = lister.getResourceName() }

    string getPkgVersionName() {
      result = lister.getApiPackage().getShortName() + "." + this.getName()
    }
  }

  class ResourceMethod extends Method {
    ResourceInterface resource;

    ResourceMethod() {
      this.getReceiverType() = resource
        and
      (this.getName() = "List" or this.getName() = "Get")
    }

    ResourceInterface getResourceInterface() { result = resource }

    string getResourceName() {
      result = resource.getResourceName()
    }

    string getVerbName() { result = "list" or result = "get" }

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
