export async function generateTravelPlan(
  destination: string,
  days: number,
  styles: string[]
): Promise<ReadableStream> {
  const styleText = styles.length > 0 ? `旅行风格偏好：${styles.join("、")}` : ""

  const response = await fetch("https://api.deepseek.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY}`,
    },
    body: JSON.stringify({
      model: "deepseek-chat",
      max_tokens: 4000,
      stream: true,
      messages: [
        {
          role: "system",
          content: `你是专业旅行规划师，只为用户指定的目的地规划行程。

        用户会告诉你目的地（如北京、巴黎、东京等）和天数，你必须严格遵守以下规则：

        ### 输出格式要求：
        1. 前半部分用生动有趣的 Markdown 写详细的旅行行程（包括每天的整体描述、建议、tips 等）。
        2. 在整个回复的最末尾，严格输出一个 JSON 代码块，格式如下，放在 \`\`\`json 和 \`\`\` 之间，不能有任何额外文字：

        \`\`\`json
        {
          "days": [
            {
              "day": 1,
              "morning": "景点名称",
              "afternoon": "景点名称",
              "evening": "景点名称或餐饮街"
            }
          ],
          "allPlaces": ["景点A", "景点B", "景点C"]
        }
        \`\`\`

        ### 严格规则（必须100%遵守）：
        - **所有景点必须真实存在于用户指定的目的地城市**，绝不能把其他城市的景点写进来（例如：用户说北京，就绝对不能出现坡子街、火宫殿、橘子洲等长沙景点）。
        - allPlaces 和 days 中的所有名称只能是该城市的真实景点、公园、博物馆、商业街、古迹等。
        - 景点名称要简短精确，例如“故宫”而不是“故宫博物院（建议游览3小时）”。
        - morning / afternoon / evening 每个时段只写**一个主要景点名称**（不要写餐厅、交通、天气、贴士等）。
        - JSON 必须是合法的、可被 JSON.parse 直接解析的，不能有多余逗号、注释或 Markdown 格式。
        - 绝不允许幻觉（hallucination）：如果不确定某个景点是否在该城市，就用该城市其他知名真实景点代替。

        用户目的地：${destination}（请严格基于此城市规划）`,
        },
        {
          role: "user",
          content: `请为我规划${destination}${days}天旅行行程。${styleText}`,
        },
      ],
    }),
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(err)
  }

  return response.body!
}