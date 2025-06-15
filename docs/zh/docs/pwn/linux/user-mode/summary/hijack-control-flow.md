---
title: 控制程序执行流
url: /pwn/linux/user-mode/summary/hijack-control-flow
tags:
- desc:control-flow-hijacking
- desc:eip-control
- desc:execution-flow-control
- desc:function-pointer-hijacking
- desc:handler-manipulation
- desc:hook-overwrite
- desc:jump-pointer-manipulation
- desc:return-address-overwrite
- desc:vtable-hijacking
- preq:arbitrary-write
- preq:free-hook-writable
- preq:heap-overflow
- preq:io-file-structure-access
- preq:malloc-hook-writable
- preq:memory-corruption
- preq:stack-overflow
- preq:write-primitive
- res:arbitrary-code-execution
- res:command-execution
- res:control-flow-hijack
- res:eip-control
- res:rip-control
- res:rop-chain-execution
- res:shellcode-execution
---
# 控制程序执行流

在控制程序执行流的过程中，我们可以考虑如下方式。

## 直接控制 EIP



## 返回地址

即控制程序栈上的返回地址。

## 跳转指针

这里我们可以考虑如下方式

- call 
- jmp

## 函数指针

常见的函数指针具有

- vtable,  function table，如 IO_FILE 的 vtable，printf function table。
- hook  指针，如 `malloc_hook`，`free_hook`。
- handler

## 修改控制流相关变量