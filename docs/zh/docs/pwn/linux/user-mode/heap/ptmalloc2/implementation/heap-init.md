---
title: 堆初始化
url: /pwn/linux/user-mode/heap/ptmalloc2/implementation/heap-init
tags:
- desc:first-allocation
- desc:heap-initialization
- desc:heap-setup
- desc:malloc-consolidate
- desc:malloc-init-state
- desc:malloc-state
- preq:first-memory-request
- preq:heap-uninitialized
- preq:user-allocation
- res:heap-initialized
- res:heap-ready
- res:malloc-state-setup
---
# 堆初始化

堆初始化是在用户第一次申请内存时执行 malloc_consolidate 再执行 malloc_init_state 实现的。这里不做过多讲解。可以参见 `malloc_state` 相关函数。