/**
 * entrypoints.ql -- 列举所有入口点
 *
 * Copyright (C) 2024 KAAAsS
 */
import go
import analyse.Function

from
    EntryFunction entryPoint
select
    // File, Start Line, Package
    entryPoint.getDeclaration().getLocation().getFile(),
    entryPoint.getDeclaration().getLocation().getStartLine(),
    entryPoint.getPackage().getPath()
