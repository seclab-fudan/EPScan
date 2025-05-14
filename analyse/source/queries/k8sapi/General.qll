/**
 * K8s API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import internal.ClientGo
import internal.ClientGoLister
import internal.ClientGoInformer
import internal.ClientGoType2
import internal.ClientGoType3
import internal.ControllerRuntime

newtype TApiCall =
  TClientGo(ClientGo::ApiCall call) or
  TClientGoLister(ClientGoLister::ApiCall call) or
  TClientGoInformer(ClientGoInformer::ApiCall call) or
  TClientGoType2(ClientGoType2::ApiCall call) or
  TClientGoType3(ClientGoType3::ApiCall call) or
  TControllerRuntime(ControllerRuntime::ApiCall call)

class K8sApiCall extends TApiCall {
  K8sApiCall() { this = this }

  ClientGo::ApiCall asClientGo() { this = TClientGo(result) }

  ClientGoLister::ApiCall asClientGoLister() { this = TClientGoLister(result) }

  ClientGoInformer::ApiCall asClientGoInformer() { this = TClientGoInformer(result) }

  ClientGoType2::ApiCall asClientGoType2() { this = TClientGoType2(result) }

  ClientGoType3::ApiCall asClientGoType3() { this = TClientGoType3(result) }

  ControllerRuntime::ApiCall asControllerRuntime() { this = TControllerRuntime(result) }

  string toString() {
    result = "CG::" + this.asClientGo().toString()
    or
    result = "CG::" + this.asClientGoLister().toString()
    or
    result = "CG::" + this.asClientGoInformer().toString()
    or
    result = "CG::" + this.asClientGoType2().toString()
    or
    result = "CG::" + this.asClientGoType3().toString()
    or
    result = "CR::" + this.asControllerRuntime().toString()
  }

  CallExpr getCall() {
    result = this.asClientGo()
    or
    result = this.asClientGoLister()
    or
    result = this.asClientGoInformer()
    or
    result = this.asClientGoType2()
    or
    result = this.asClientGoType3()
    or
    result = this.asControllerRuntime()
  }

  string getVerbName() {
    result = this.asClientGo().getVerbName()
    or
    result = this.asClientGoLister().getVerbName()
    or
    result = this.asClientGoInformer().getVerbName()
    or
    result = this.asClientGoType2().getVerbName()
    or
    result = this.asClientGoType3().getVerbName()
    or
    result = this.asControllerRuntime().getVerbName()
  }

  string getResourceName() {
    result = this.asClientGo().getResourceName()
    or
    result = this.asClientGoLister().getResourceName()
    or
    result = this.asClientGoInformer().getResourceName()
    or
    result = this.asClientGoType2().getResourceName()
    or
    result = this.asClientGoType3().getResourceName()
    or
    result = this.asControllerRuntime().getResourceName()
  }

  string getApiType() {
    this instanceof TClientGo and result = "client-go"
    or
    this instanceof TClientGoLister and result = "client-go"
    or
    this instanceof TClientGoInformer and result = "client-go"
    or
    this instanceof TClientGoType2 and result = "client-go"
    or
    this instanceof TClientGoType3 and result = "client-go"
    or
    this instanceof TControllerRuntime and result = "controller-runtime"
  }

  Location getLocation() { result = this.getCall().getLocation() }
}
