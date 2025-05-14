/**
 * 候选 K8s API 调用点的识别
 *
 * Copyright (C) 2024 KAAAsS
 */

import internal.ClientGo
import internal.ControllerRuntime

newtype TCandidateApiCall =
  TCandidateControllerRuntime(ControllerRuntime::CandidateApiCall call)

class CandidateApiCall extends TCandidateApiCall {
  CandidateApiCall() { this = this }

  ControllerRuntime::CandidateApiCall asControllerRuntime() { this = TCandidateControllerRuntime(result) }

  string toString() {
    result = "Cand::CR::" + this.asControllerRuntime().toString()
  }

  CallExpr getCall() {
    result = this.asControllerRuntime()
  }

  string getVerbName() {
    result = this.asControllerRuntime().getVerbName()
  }

  string getTypeHint() {
    result = this.asControllerRuntime().getTypeHint()
  }

  string getApiType() {
    this instanceof TCandidateControllerRuntime and result = "controller-runtime"
  }

  Location getLocation() { result = this.getCall().getLocation() }
}
