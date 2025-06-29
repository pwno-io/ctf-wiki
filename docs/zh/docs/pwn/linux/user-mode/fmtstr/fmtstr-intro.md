---
title: 原理介绍
url: /pwn/linux/user-mode/fmtstr/fmtstr-intro
tags:
- desc:format-string
- desc:printf-family
- desc:stack-based
- desc:variadic-function
- preq:no-format-string-validation
- preq:printf-scanf-functions
- preq:stack-access
- preq:user-controlled-format-string
- res:arbitrary-read
- res:arbitrary-write
- res:information-disclosure
- res:memory-leak
- res:program-crash
- res:stack-content-leak
---
# 原理介绍

首先，对格式化字符串漏洞的原理进行简单介绍。

## 格式化字符串函数介绍

格式化字符串函数可以接受可变数量的参数，并将**第一个参数作为格式化字符串，根据其来解析之后的参数**。通俗来说，格式化字符串函数就是将计算机内存中表示的数据转化为我们人类可读的字符串格式。几乎所有的C/C++程序都会利用格式化字符串函数来**输出信息，调试程序，或者处理字符串**。一般来说，格式化字符串在利用的时候主要分为三个部分

- 格式化字符串函数
- 格式化字符串
- 后续参数，**可选**

这里我们给出一个简单的例子，其实相信大多数人都接触过printf函数之类的。之后我们再一个一个进行介绍。

![](./figure/printf.png)

### 格式化字符串函数

常见的有格式化字符串函数有

-   输入
    -   scanf
-   输出

|           函数            |        基本介绍         |
| :---------------------: | :-----------------: |
|         printf          |      输出到stdout      |
|         fprintf         |     输出到指定FILE流      |
|         vprintf         | 根据参数列表格式化输出到 stdout |
|        vfprintf         | 根据参数列表格式化输出到指定FILE流 |
|         sprintf         |       输出到字符串        |
|        snprintf         |     输出指定字节数到字符串     |
|        vsprintf         |   根据参数列表格式化输出到字符串   |
|        vsnprintf        | 根据参数列表格式化输出指定字节到字符串 |
|      setproctitle       |       设置argv        |
|         syslog          |        输出日志         |
| err, verr, warn, vwarn等 |         。。。         |

### 格式化字符串

这里我们了解一下格式化字符串的格式，其基本格式如下

```
%[parameter][flags][field width][.precision][length]type
```
每一种pattern的含义请具体参考维基百科的[格式化字符串](https://zh.wikipedia.org/wiki/%E6%A0%BC%E5%BC%8F%E5%8C%96%E5%AD%97%E7%AC%A6%E4%B8%B2) 。以下几个pattern中的对应选择需要重点关注

-   parameter
    -   n$，获取格式化字符串中的指定参数
-   flag
-   field width
    -   输出的最小宽度
-   precision
    -   输出的最大长度
-   length，输出的长度
    -   hh，输出一个字节
    -   h，输出一个双字节
-   type
    -   d/i，有符号整数
    -   u，无符号整数
    -   x/X，16进制unsigned int 。x使用小写字母；X使用大写字母。如果指定了精度，则输出的数字不足时在左侧补0。默认精度为1。精度为0且值为0，则输出为空。
    -   o，8进制unsigned int 。如果指定了精度，则输出的数字不足时在左侧补0。默认精度为1。精度为0且值为0，则输出为空。
    -   s，如果没有用l标志，输出null结尾字符串直到精度规定的上限；如果没有指定精度，则输出所有字节。如果用了l标志，则对应函数参数指向wchar\_t型的数组，输出时把每个宽字符转化为多字节字符，相当于调用wcrtomb 函数。
    -   c，如果没有用l标志，把int参数转为unsigned char型输出；如果用了l标志，把wint\_t参数转为包含两个元素的wchart_t数组，其中第一个元素包含要输出的字符，第二个元素为null宽字符。
    -   p， void \*型，输出对应变量的值。printf("%p",a)用地址的格式打印变量a的值，printf("%p", &a)打印变量a所在的地址。
    -   n，不输出字符，但是把已经成功输出的字符个数写入对应的整型指针参数所指的变量。
    -   %， '``%``'字面值，不接受任何flags, width。

### 参数

就是相应的要输出的变量。

## 格式化字符串漏洞原理

在一开始，我们就给出格式化字符串的基本介绍，这里再说一些比较细致的内容。我们上面说，格式化字符串函数是根据格式化字符串来进行解析的 。**那么相应的要被解析的参数的个数也自然是由这个格式化字符串所控制**。比如说'%s'表明我们会输出一个字符串参数。

我们再继续以上面的为例子进行介绍

![基本例子](./figure/printf.png)

对于这样的例子，在进入printf函数的之前(即还没有调用printf)，栈上的布局由高地址到低地址依次如下

```text
some value
3.14
123456
addr of "red"
addr of format string: Color %s...
```

**注：这里我们假设3.14上面的值为某个未知的值。**

在进入printf之后，函数首先获取第一个参数，一个一个读取其字符会遇到两种情况

-   当前字符不是%，直接输出到相应标准输出。
-   当前字符是%， 继续读取下一个字符
    -   如果没有字符，报错
    -   如果下一个字符是%,输出%
    -   否则根据相应的字符，获取相应的参数，对其进行解析并输出

那么假设，此时我们在编写程序时候，写成了下面的样子

```C
printf("Color %s, Number %d, Float %4.2f");
```

此时我们可以发现我们并没有提供参数，那么程序会如何运行呢？程序照样会运行，会将栈上存储格式化字符串地址上面的三个变量分别解析为

1. 解析其地址对应的字符串
2. 解析其内容对应的整形值
3. 解析其内容对应的浮点值

对于2，3来说倒还无妨，但是对于对于1来说，如果提供了一个不可访问地址，比如0，那么程序就会因此而崩溃。

这基本就是格式化字符串漏洞的基本原理了。

## 参考阅读

- https://zh.wikipedia.org/wiki/%E6%A0%BC%E5%BC%8F%E5%8C%96%E5%AD%97%E7%AC%A6%E4%B8%B2
