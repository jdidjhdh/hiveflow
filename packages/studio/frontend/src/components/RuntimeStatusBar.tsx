import { useEffect } from 'react';
import { Space, Tag, Switch, Tooltip } from 'antd';
import { RobotOutlined, ApartmentOutlined } from '@ant-design/icons';
import { useEngineStore } from '@/store/useEngineStore';
import { useAgentRuntimeStore } from '@/store/useAgentRuntimeStore';
import { getErrorMessage } from '@/utils/api';
import { App } from 'antd';

export default function RuntimeStatusBar() {
  const { message } = App.useApp();
  const engineMode = useEngineStore(s => s.mode);
  const runtimeMode = useAgentRuntimeStore(s => s.runtimeMode);
  const skills = useAgentRuntimeStore(s => s.skills);
  const loading = useAgentRuntimeStore(s => s.loading);
  const fetchRuntime = useAgentRuntimeStore(s => s.fetchRuntime);
  const setRuntimeMode = useAgentRuntimeStore(s => s.setRuntimeMode);

  useEffect(() => {
    if (engineMode === 'real') {
      fetchRuntime();
    }
  }, [engineMode, fetchRuntime]);

  if (engineMode !== 'real') {
    return null;
  }

  const isAgent = runtimeMode === 'agent';
  const tooltip = isAgent
    ? `HiveMindApp：自然语言 run_query / 自动 Skill 图${skills.length ? `（${skills.length} 个 Skill）` : ''}`
    : 'Core DAG：画布工作流 / Skill 图编排执行';

  const handleToggle = async (checked: boolean) => {
    try {
      await setRuntimeMode(checked ? 'agent' : 'core');
      message.success(checked ? '全局运行时：Agent 模式' : '全局运行时：Core 模式');
    } catch (e) {
      message.error(getErrorMessage(e));
    }
  };

  return (
    <Space size="middle" className="hf-header-runtime" data-testid="header-runtime-bar">
      <Tooltip title={tooltip}>
        <Tag
          icon={isAgent ? <RobotOutlined /> : <ApartmentOutlined />}
          color={isAgent ? 'purple' : 'blue'}
        >
          {isAgent ? 'Agent' : 'Core'}
        </Tag>
      </Tooltip>
      {isAgent && skills.length > 0 && (
        <Tooltip title={skills.join(', ')}>
          <Tag color="geekblue">{skills.length} Skills</Tag>
        </Tooltip>
      )}
      <Tooltip title="切换后端运行时（编排器、设置、能力市场同步）">
        <Switch
          size="small"
          checked={isAgent}
          loading={loading}
          checkedChildren="Agent"
          unCheckedChildren="Core"
          onChange={handleToggle}
          data-testid="header-runtime-switch"
        />
      </Tooltip>
    </Space>
  );
}
