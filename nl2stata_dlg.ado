*! nl2stata_dlg 2.0.0  2026-05-07
*! 对话框提交处理：从 dialog 生成的命令接收参数 → 翻译 → 显示结果
*! 命令格式: nl2stata_dlg <prompt_words...> <model> <apikey>
*!   末 2 个 token 是 model 和 apikey，其余拼成 prompt


* ---- 翻译子程序 ----
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

    * 调用 Python（通过系统 shell）
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


* ---- 对话框主程序 ----
capture program drop nl2stata_dlg
program define nl2stata_dlg

    * 从 token 列表解析：后两个是 model 和 apikey
    local n : word count `0'

    if `n' < 3 {
        display as error "请先输入你的需求！"
        exit 198
    }

    * 倒数第 1 个 token = apikey
    local apikey : word `n' of `0'

    * 倒数第 2 个 token = model
    local m = `n' - 1
    local model : word `m' of `0'

    * 前 n-2 个 token 拼成 prompt
    local p_end = `n' - 2
    local prompt ""
    forvalues i = 1/`p_end' {
        local w : word `i' of `0'
        if `i' == 1 {
            local prompt = `"`w'"'
        }
        else {
            local prompt = `"`prompt' `w'"'
        }
    }

    * 校验
    if `"`prompt'"' == "" {
        display as error "请先输入你的需求！"
        exit 198
    }
    if "`apikey'" == "" {
        local apikey : env DEEPSEEK_API_KEY
    }
    if "`apikey'" == "" {
        display as error "请填写 API Key 或设置环境变量 DEEPSEEK_API_KEY！"
        exit 198
    }
    if "`model'" == "" {
        local model "deepseek-v4-pro"
    }

    * 保存模型
    capture char _dta[_nl2stata_model] "`model'"

    * 翻译
    l__translate_dialog `"`prompt'"' "`model'" "`apikey'"
    local translated = r(commands)

    * 兜底清洗：字面量 \n → 真正换行
    local bn = char(92) + "n"
    local translated = subinstr(`"`translated'"', "`bn'", char(10), .)

    if `"`translated'"' == "" | strpos(`"`translated'"', "* ERROR:") == 1 {
        display as error `"`translated'"'
        exit 1
    }

    display as text _newline "生成的 Stata 命令："
    display as result `"`translated'"'

    ExecuteCommands `"`translated'"'
end
