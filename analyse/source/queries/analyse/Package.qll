/**
 * 包相关的查询
 *
 * Copyright (C) 2024 KAAAsS
 */
import go

class PackagedFile extends GoFile {
    Package pkg;
    
    PackagedFile() {
        exists(Entity e
            | e.getDeclaration().getFile() = this 
            | e.getPackage() = pkg )
    }

    Package getPackage() { result = pkg }
}

predicate packageImports(Package parent, Package imported) {
    exists(ImportSpec spec, PackagedFile pkgFile
        | pkgFile.getPackage() = parent
        | spec.getParent+() = pkgFile and spec.getPath() = imported.getPath())
}
