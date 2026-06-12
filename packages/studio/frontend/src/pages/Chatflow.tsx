import { ChatflowToolbar } from '@/components/chatflow/ChatflowToolbar';
import { ChatflowCanvas } from '@/components/chatflow/ChatflowCanvas';
import { ChatflowPreviewPanel } from '@/components/chatflow/ChatflowPreviewPanel';
import { ChatflowNodeDrawer } from '@/components/chatflow/ChatflowNodeDrawer';
import { useChatflowPage } from '@/components/chatflow/hooks/useChatflowPage';

export default function ChatflowPage() {
  const p = useChatflowPage();

  return (
    <div style={{ height: 'calc(100vh - 64px - 24px)', display: 'flex', gap: 16 }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <ChatflowToolbar
          engineMode={p.engineMode}
          agentAvailable={p.agentAvailable}
          useAgentMode={p.useAgentMode}
          nodeCount={p.nodeCount}
          onUseAgentModeChange={p.setUseAgentMode}
          onAddNode={p.addNode}
          onSave={() => void p.saveChatflow()}
          onLoad={() => void p.loadChatflow()}
          onExecute={() => void p.executeChatflow()}
          onClear={p.clearCanvas}
        />
        <ChatflowCanvas
          nodes={p.nodes}
          edges={p.edges}
          onNodesChange={p.onNodesChange}
          onEdgesChange={p.onEdgesChange}
          onConnect={p.onConnect}
          onNodeClick={p.onNodeClick}
        />
      </div>

      <ChatflowPreviewPanel
        messages={p.chatMessages}
        chatInput={p.chatInput}
        agentLoading={p.agentLoading}
        agentAvailable={p.agentAvailable}
        useAgentMode={p.useAgentMode}
        lastIntentId={p.lastIntentId}
        onInputChange={p.setChatInput}
        onSend={p.handleSendMessage}
        onPlanOnly={p.handlePlanOnlyFromChat}
        onClearMessages={() => p.setChatMessages([])}
      />

      <ChatflowNodeDrawer
        open={p.drawerOpen}
        selectedNode={p.selectedNode}
        form={p.form}
        onClose={() => p.setDrawerOpen(false)}
        onSave={() => void p.saveNodeChanges()}
        onDelete={p.deleteNode}
      />
    </div>
  );
}
