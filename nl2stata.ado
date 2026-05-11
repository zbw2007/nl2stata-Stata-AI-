*! nl2stata 2.0.0  2026-05-07
*! 将自然语言指令翻译为 Stata 命令（基于 DeepSeek 大模型）
*!
*! 用法:
*!   命令行: nl2stata "你的自然语言指令" [, EXECute noASK Model(string) ApiKey(string)]
*!   对话框: db nl2stata

capture program drop nl2stata
program define nl2stata
    version 16.0
    syntax [anything] [, EXECute noASK Model(string) ApiKey(string)]

    * ---- 无参数：启动图形对话框 ----
    if `"`anything'"' == "" {
        db nl2stata
        exit
    }

    * ---- 命令行模式 ----
    local user_prompt = `"`anything'"'

    * 模型默认值
    if "`model'" == "" {
        capture local model : char _dta[_nl2stata_model]
        if _rc != 0 | "`model'" == "" {
            local model "deepseek-v4-pro"
        }
    }

    * API Key
    if "`apikey'" == "" {
        local apikey : env DEEPSEEK_API_KEY
        if "`apikey'" == "" {
            display as error "请提供 API Key（通过 ApiKey() 选项或设置环境变量 DEEPSEEK_API_KEY）"
            exit 198
        }
    }

    * 保存模型
    capture char _dta[_nl2stata_model] "`model'"

    * 翻译
    l__translate_dialog `"`user_prompt'"' "`model'" "`apikey'"
    local translated = r(commands)

    * 兜底清洗：字面量 \n → 真正换行
    local bn = char(92) + "n"
    local translated = subinstr(`"`translated'"', "`bn'", char(10), .)

    * 检查错误
    if `"`translated'"' == "" | strpos(`"`translated'"', "* ERROR:") == 1 {
        display as error `"`translated'"'
        exit 1
    }

    * 显示并执行
    display as text _newline "生成的 Stata 命令："
    display as result `"`translated'"'
    ExecuteCommands `"`translated'"'
end


* ---- 辅助子程序：调用 Python 翻译 ----
capture program drop l__translate_dialog
program define l__translate_dialog, rclass
    args prompt model apikey

    * 找到 Python 脚本
    local scriptdir = c(sysdir_personal) + "n/"
    capture confirm file "`scriptdir'nl2stata.py"
    if _rc != 0 {
        local scriptdir = c(pwd) + "/"
        capture confirm file "`scriptdir'nl2stata.py"
        if _rc != 0 {
            return local commands "* ERROR: Cannot find nl2stata.py"
            exit
        }
    }
    local scriptpath = "`scriptdir'nl2stata.py"

    * 将 prompt 写入临时文件
    tempfile infile
    tempfile outfile
    tempname fhin
    file open `fhin' using `"`infile'"', write text
    file write `fhin' `"`prompt'"' _n
    file close `fhin'

    * 调用 Python（通过系统 shell，避免依赖 Stata Python 集成）
    capture shell python "`scriptpath'" "`infile'" "`outfile'" "`model'" "`apikey'"

    if _rc != 0 {
        return local commands "* ERROR: Python script failed - check Python installation (python --version)"
        exit
    }

    * 读取输出
    tempname fhout
    file open `fhout' using `"`outfile'"', read text
    file read `fhout' line
    local result = `"`line'"'
    while r(eof) == 0 {
        file read `fhout' line
        if r(eof) == 0 {
            local result = `"`result'\n`line'"'
        }
    }
    file close `fhout'

    return local commands = `"`result'"'
end


* ---- 执行多行命令块（#delimit ; 模式，支持多行命令） ----
capture program drop ExecuteCommands
program define ExecuteCommands
    args cmdblock

    * 构建带 #delimit ; 的完整命令块
    local block = "#delimit cr" + char(10) + "#delimit ;" + char(10) + `"`cmdblock'"' + char(10) + "#delimit cr"

    display as text ">> 执行命令块："
    display as result `"`cmdblock'"'

    * 写入临时 do 文件并执行
    tempfile dofile
    tempname fhdo
    file open `fhdo' using `"`dofile'"', write text
    file write `fhdo' `"`block'"' _n
    file close `fhdo'

    capture noisily do `"`dofile'"' nostop
    if _rc != 0 {
        display as error "命令执行出错（错误代码 r(_rc)），已停止。"
        exit
    }
end
