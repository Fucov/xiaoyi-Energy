import { Sidebar } from '@/components/layout/Sidebar'
import { ChatArea } from '@/components/chat/ChatArea'
import { AnalysisPanel } from '@/components/layout/AnalysisPanel'

export default function Home() {
  return (
    <div className="flex h-screen gradient-mesh">
      {/* 左侧栏 */}
      <Sidebar />
      
      {/* 主对话区 */}
      <ChatArea />
      
      {/* 右侧分析面板 */}
      <AnalysisPanel />
    </div>
  )
}
