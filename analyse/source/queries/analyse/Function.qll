/**
 * 函数相关的查询
 *
 * Copyright (C) 2024 KAAAsS
 */

import go
import Package

Function getParentFunction(Expr expr) { result = expr.getParent*().(FuncDecl).getFunction() }

class EntryFunction extends Function {
  EntryFunction() { this.hasQualifiedName(_, "main") }
}

class InitFunction extends Function {
  InitFunction() { this.getName() = "init" }

  Package getActualPackage() {
    exists(PackagedFile pkgFile
      | this.getFuncDecl().getFile() = pkgFile
      | result = pkgFile.getPackage())
  }
}

predicate initCalling(EntryFunction entry, InitFunction init) {
  packageImports*(entry.getPackage(), init.getActualPackage())
}
