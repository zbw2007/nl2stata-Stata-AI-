#!/usr/bin/env python
"""nl2stata 翻译核心：调用 DeepSeek API 将自然语言翻译为 Stata 命令。

用法:
  文件 I/O 模式（Stata ado 调用）:
    python nl2stata.py <infile> <outfile> <model> <apikey>

  命令行模式:
    python nl2stata.py <prompt> <model> <apikey> [--output-file <path>]
"""

import sys

SYSTEM_PROMPT = (
    "你是一个把自然语言翻译成 Stata 16 命令的助手。只返回纯 Stata 命令，不要 markdown/解释/代码块。\n"
    "不要使用 clear 除非用户明确要求。用户描述不清时给出最合理的猜测命令。\n"
    "每条命令必须以 ; 结尾（; 代替换行作为命令分隔符）。\n"
    "多行命令（循环、if-else、程序定义等）正常换行书写，整个结构以 ; 结尾。\n"
    "例如需要三条命令时输出：\n"
    "  summarize price, detail;\n"
    "  regress price mpg;\n"
    "  predict yhat, xb;\n"
    "循环示例：\n"
    "  foreach var of varlist price mpg {\n"
    "      summarize `var', detail;\n"
    "  };\n"
    "严禁使用 Stata 行接续符: /// 和 \\\n和 \\\\，命令之间只用 ; 分隔即可。\n\n"

    "=== Stata 语法参考 ===\n\n"

    "【命令基本结构】\n"
    "  command [varlist] [if condition] [, options]\n"
    "  示例: regress mpg weight length if gear_ratio < 3, beta\n"
    "  if 前不能有逗号！错误: summarize price, if price>5000\n"
    "                           正确: summarize price if price>5000\n\n"

    "【if 条件运算符】\n"
    "  == 等于  > 大于  < 小于  >= 大于等于  <= 小于等于  != 不等于\n"
    "  & 且  | 或  赋值用 =（gen newvar = 2） 判断相等用 ==（if x == 5）\n\n"

    "【数据导入与导出】\n"
    "  use \"mydata.dta\", clear\n"
    "  sysuse auto, clear\n"
    "  import excel \"data.xlsx\", sheet(\"Sheet1\") firstrow clear\n"
    "  import delimited \"data.csv\", clear\n"
    "  import delimited \"data.csv\", encoding(utf-8) clear\n"
    "  save \"clean_data.dta\", replace\n"
    "  export excel \"file.xlsx\", firstrow(variables) replace\n"
    "  export delimited \"file.csv\", replace\n"
    "  注意: csv/xlsx 不能用 use 加载，必须用 import\n\n"

    "【数据查看与清洗】\n"
    "  describe / des            查看变量信息\n"
    "  codebook, compact         详细描述变量取值、缺失值\n"
    "  summarize varlist, detail 描述性统计\n"
    "  list varlist in 1/10      列出前10条\n"
    "  drop varlist              删除变量\n"
    "  drop if age<18            删除满足条件的观测值\n"
    "  keep varlist              保留指定变量\n"
    "  rename oldname newname    重命名变量\n"
    "  label variable age \"受访者年龄\"\n"
    "  encode stringvar, gen(numvar) 字符串→数值标签\n"
    "  decode numvar, gen(strvar)    数值标签→字符串\n"
    "  destring var, replace force   字符型转数值型\n"
    "  tostring var, replace         数值型转字符型\n\n"

    "【缺失值与异常值处理】\n"
    "  missing(var)        判断是否为缺失值\n"
    "  ipolate var timevar, gen(newvar)  线性插值填补缺失\n"
    "  duplicates list varlist            查找重复值\n"
    "  duplicates drop varlist, force     删除重复观测\n"
    " 缺失值用 . 表示，不是 NA / null / NaN\n\n"

    "【变量创建与修改】\n"
    "  generate newvar = expression    创建新变量（可缩写 gen）\n"
    "  replace oldvar = expression     修改已存在变量（不可缩写）\n"
    "  egen newvar = mean(x)           均值\n"
    "  egen newvar = sd(x)             标准差\n"
    "  egen newvar = rowmean(varlist)  行均值\n"
    "  egen newvar = rowtotal(varlist) 行总和\n"
    "  egen newvar = total(x), by(group)  分组求和\n\n"

    "【数据合并与管理】\n"
    "  sort id year               排序\n"
    "  by id: egen mean_x = mean(x) 分组操作（需先 sort）\n"
    "  merge 1:1 id using \"other.dta\"   一对一合并（增加变量）\n"
    "  merge m:1 id using \"other.dta\"   多对一合并\n"
    "  merge 1:m id using \"other.dta\"   一对多合并\n"
    "  append using \"more.dta\"       追加数据集（增加观测）\n"
    "  reshape wide var, i(id) j(year)\n"
    "  reshape long var, i(id) j(year)\n"
    "  collapse (mean) v1 (sum) v2, by(group)\n\n"

    "【描述性统计与检验】\n"
    "  summarize varlist, detail\n"
    "  tabulate var\n"
    "  tabulate var1 var2, row col chi2\n"
    "  correlate varlist              相关系数矩阵\n"
    "  pwcorr varlist, sig            带显著性星号\n"
    "  ttest var, by(groupvar)        t 检验\n"
    "  ttest var == 0                 单样本 t 检验\n\n"

    "【回归模型】\n"
    "  regress y x1 x2                OLS 线性回归\n"
    "  regress y x1 x2, robust        稳健标准误\n"
    "  regress y x1 x2, noconstant    过原点回归\n"
    "  regress y i.catvar             因子变量 — i.前缀表示分类变量\n"
    "  regress y c.x##c.x             平方项\n"
    "  regress y x1##x2               交互项(含主效应)\n"
    "  regress y x1#x2                仅交互项\n"
    "  logit y x1 x2 / probit y x1 x2 二分类回归\n"
    "  ivregress 2sls y x1 (x2 = z)   工具变量\n"
    "  areg y x1, absorb(id)          固定效应\n"
    "  ivreghdfe y x1 (x2=z), absorb(id)  高维固定效应IV\n\n"

    "【分组回归】\n"
    "  by group: regress y x          逐组回归（需先 sort group）\n"
    "  statsby, by(group): regress y x  按组回归并汇总系数\n"
    "  bysort group: egen newvar = mean(x)  按组计算均值\n\n"

    "【预测与边际效应】\n"
    "  predict yhat, xb               线性预测值\n"
    "  predict resid, residuals        残差\n"
    "  margins, dydx(*)               平均边际效应\n"
    "  margins, at(x=(0(1)10))        指定值处的边际效应\n"
    "  marginsplot                    边际效应图\n"
    "  test x1=x2=0                   F 检验\n"
    "  test x1=x2                     系数相等检验\n"
    "  lincom x1+x2                   线性组合\n\n"

    "【绘图】\n"
    "  histogram var, frequency / density\n"
    "  histogram var, by(groupvar)\n"
    "  scatter y x / twoway scatter y x\n"
    "  twoway (scatter y x) (lfit y x)\n"
    "  graph box y, over(groupvar)\n"
    "  graph bar (mean) y, over(groupvar)\n"
    "  line y x, sort / twoway line y year, sort\n"
    "  多子图用 by() 选项: histogram x, by(group)\n\n"

    "【编程与自动化】\n"
    "  local name \"value\" / global name \"value\"  定义宏\n"
    "  foreach var of varlist var1-var10 { ... }\n"
    "  forvalues i = 1/10 { ... }\n"
    "  if ... { ... } else { ... }\n\n"

    "【常用陷阱】\n"
    "  - 赋值用 =，判断相等用 ==（不可混淆）\n"
    "  - 缺失值是 .，判断缺失用 missing(var)\n"
    "  - 字符串用双引号: keep if name == \"Bob\"\n"
    "  - 变量名不能以数字开头，不能含空格\n"
    "  - options 以逗号开头: su age, detail（逗号前可空格，逗号后不可空格）\n"
    "  - replace 不可缩写（gen 可以缩写）\n"
    "  - regress 可缩写为 reg\n"
    "  - by 前缀前需要先 sort\n"
    "  - 不能用 use 加载 csv/xlsx（用 import）\n"
    "  - 多命令块中，后一条命令依赖前一条生成的新变量时，不要用 capture\n"
    "  - 避免在代码中硬编码具体数值或阈值\n"
)


def translate(prompt: str, model: str, api_key: str) -> str:
    """调用 DeepSeek API 翻译自然语言为 Stata 命令。"""

    try:
        from openai import OpenAI
    except ImportError:
        return "* ERROR: Python environment issue - please install openai package (pip install openai)"

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=300)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1000,
        )

        result = response.choices[0].message.content.strip()

        # 清洗常见的 LLM 输出污染
        result = result.replace("```stata", "").replace("```", "")  # markdown 代码块
        result = result.replace("`", "")                             # 行内代码标记
        result = result.replace("* ", "")                            # markdown 列表
        # 反斜杠转义清理（在逐行处理之前，顺序重要）
        result = result.replace("\\n", "\n")                         # 字面量 \n → 真正换行
        result = result.replace("\\\n", "\n")                        # 行尾接续符
        result = result.replace("\\\\", "")                          # 双反斜杠残余

        # 逐行清洗
        lines = result.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            # 跳过空行
            if not line:
                continue
            # 跳过纯接续符行
            if line in ("///", "\\", "//"):
                continue
            # 移除行首接续符
            if line.startswith("/// "):
                line = line[4:]
            if line.startswith("\\ "):
                line = line[2:]
            # 移除行尾接续符
            if line.endswith(" ///"):
                line = line[:-4].rstrip()
            if line.endswith(" \\"):
                line = line[:-2].rstrip()
            # 跳过 markdown 标题和分隔线
            if line.startswith("#") or line.startswith("---"):
                continue
            # 跳过 #delimit 指令（由 ADO 代码自行添加）
            if line.strip().startswith("#delimit"):
                continue
            if line:
                cleaned.append(line)

        # 确保每行命令以 ; 结尾（AI 可能不严格遵守提示词）
        for idx in range(len(cleaned)):
            line = cleaned[idx].rstrip()
            if line and not line.endswith(";") and not line.endswith("{"):
                cleaned[idx] = line + ";"

        return "\n".join(cleaned)

    except ImportError:
        return "* ERROR: Python environment issue - please install openai package (pip install openai)"
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return "* ERROR: Invalid API Key"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return "* ERROR: Request timed out"
        elif "402" in error_msg or "insufficient" in error_msg.lower() or "balance" in error_msg.lower():
            return "* ERROR: Insufficient balance"
        else:
            return f"* ERROR: {error_msg}"


def main():
    args = sys.argv[1:]

    if not args:
        print("* ERROR: Missing arguments")
        sys.exit(1)

    # 判断是否为文件 I/O 模式（前 4 个参数均为文件路径风格或共 4 个参数）
    # 文件 I/O 模式: <infile> <outfile> <model> <apikey>
    # 命令行模式:    <prompt> <model> <apikey> [--output-file <path>]
    if len(args) == 4:
        # 文件 I/O 模式
        infile, outfile, model, api_key = args
        with open(infile, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
        result = translate(prompt, model, api_key)
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        # 命令行模式
        output_file = None
        positional = []
        i = 0
        while i < len(args):
            if args[i] == "--output-file" and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            else:
                positional.append(args[i])
                i += 1

        if len(positional) < 3:
            print("* ERROR: Missing arguments. Usage: python nl2stata.py <prompt> <model> <apikey> [--output-file <path>]")
            sys.exit(1)

        prompt, model, api_key = positional[0], positional[1], positional[2]
        result = translate(prompt, model, api_key)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            print(result)


if __name__ == "__main__":
    main()
