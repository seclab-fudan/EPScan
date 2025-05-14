/**
 * 全局变量的建模
 *
 * Copyright (C) 2024 KAAAsS
 */
import go

class GlobalVar extends ValueEntity {
    GlobalVar() {
        this.getDeclaration().getParent().getParent().getParent() instanceof File
    }

    GlobalVarAssign getDeclAssign() {
        result = this.getDeclaration().getParent()
    }
}

class GlobalVarAssign extends ValueSpec {
    GlobalVarAssign() {
        this.getParent().getParent() instanceof File
    }

    ValueEntity getVar() {
        result.getDeclaration().getParent() = this
    }

    ValueEntity getAUsedVar() {
        result.getAReference().getParent() = this.getInit()
    }
}