/**
 * 引用图
 *
 * Copyright (C) 2024 KAAAsS
 */

import go
import GlobalVar

module RefReleation {
  private import Function

  predicate cgEdge(Function a, Function b) { b.getACall().getRoot().(FuncDecl).getFunction() = a }

  predicate methodRefEdge(Function a, Function b) {
    b.getAReference().getParent+().(FuncDecl).getFunction() = a and
    a != b
  }

  predicate entryCallInit(Function a, Function b) {
      initCalling(a, b)
  }

  predicate gvDefByFunction(GlobalVar gv, Function f) {
    gv.getDeclAssign() = f.getAReference().getParent+().(GlobalVarAssign)
  }

  predicate functionUseGv(Function f, GlobalVar gv) {
    f.getBody() = gv.getAReference().getParent+()
  }

  predicate gvDefByGv(GlobalVar gv, GlobalVar gvUsed) { gv.getDeclAssign().getAUsedVar() = gvUsed }

  predicate methodToReceiverType(Type typ, Function f) {
    f.getFuncDecl()
        .getAChild()
        .(ReceiverDecl)
        .getAChild*()
        .(TypeName)
        .getType() = typ
  }

  predicate isNamedStructType(Type typ) {
    typ.(NamedType).getUnderlyingType() instanceof StructType
  }

  predicate typeRefInFunction(Function f, Type typ) {
    isNamedStructType(typ) and
    typ.getEntity().getAReference().getParent*() = f.getBody()
  }
}

module RefGraph {
  newtype TPathNode =
    TFunction(Function f) or
    TGlobalVar(GlobalVar v) or
    TType(Type t)

  private predicate blackListNode(PathNode node) {
    none()
  }

  private predicate blackListEdge(PathNode src, PathNode dst) { none() }

  class PathNode extends TPathNode {
    Function asFunction() { this = TFunction(result) }

    GlobalVar asGlobalVar() { this = TGlobalVar(result) }

    Type asType() { this = TType(result) }

    string toString() {
      result = this.asFunction().toString()
      or
      result = this.asGlobalVar().toString()
      or
      result = this.asType().toString()
    }

    PathNode getASuccessor() {
      not blackListNode(this) and
      not blackListEdge(this, result) and
      (
        RefReleation::cgEdge(this.asFunction(), result.asFunction())
        or
        RefReleation::methodRefEdge(this.asFunction(), result.asFunction())
        or
        RefReleation::entryCallInit(this.asFunction(), result.asFunction())
        or
        RefReleation::functionUseGv(this.asFunction(), result.asGlobalVar())
        or
        RefReleation::typeRefInFunction(this.asFunction(), result.asType())
        or
        RefReleation::gvDefByGv(this.asGlobalVar(), result.asGlobalVar())
        or
        RefReleation::gvDefByFunction(this.asGlobalVar(), result.asFunction())
        or
        RefReleation::methodToReceiverType(this.asType(), result.asFunction())
      )
    }

    Location getLocation() {
      result = this.asFunction().getDeclaration().getLocation()
      or
      result = this.asGlobalVar().getDeclaration().getLocation()
      or
      result = this.asType().getEntity().getDeclaration().getLocation()
    }
  }

  predicate edges(RefGraph::PathNode pred, RefGraph::PathNode succ) { pred.getASuccessor() = succ }
}
