import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from 'file:///C:/Users/demo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load('C:/Users/demo/Downloads/测试月计划-导入模板.xlsx'));
const s = wb.worksheets.getItem('训练计划');
const topics = [
 ['Cisco','交换机初始配置与管理访问','Cisco','VLAN 划分与 802.1Q 中继配置'],
 ['Linux','Linux 用户、组与文件权限管理','Linux','使用 systemd 管理服务并排查启动故障'],
 ['Windows','Windows Server 安装与基础配置','Windows','部署 AD DS 并规划组织单位'],
 ['Cisco','IPv4 子网划分与静态路由配置','Cisco','配置单臂路由并验证跨 VLAN 通信'],
 ['Linux','部署 DNS 正反向解析服务','Windows','配置域内 DNS 并验证客户端解析'],
 ['综合','第一周基础设施限时搭建','综合','复盘连通性、配置备份与评分点'],
 ['Cisco','OSPF 单区域邻接与路由发布','Cisco','排查 OSPF 邻接和路由收敛故障'],
 ['Windows','部署 DHCP 作用域与地址保留','Windows','配置 DHCP 中继并测试地址分配'],
 ['Linux','配置 SSH 密钥认证与访问控制','Linux','配置防火墙规则并验证最小开放端口'],
 ['Cisco','生成树协议与二层环路防护','Cisco','配置链路聚合并验证冗余切换'],
 ['Windows','组策略配置与客户端策略验证','Windows','部署共享文件夹并设置 NTFS 权限'],
 ['综合','网络与目录服务综合限时训练','综合','检查交付文档并复盘失分项'],
 ['Linux','部署 Nginx 虚拟主机与 HTTPS','Linux','配置证书并验证站点访问与日志'],
 ['Windows','部署 IIS 站点与 TLS 绑定','Windows','配置域证书服务并申请服务器证书'],
 ['Cisco','配置 ACL 控制网段间访问','Cisco','配置 NAT 并验证内外网访问策略'],
 ['Linux','部署文件共享并配置用户访问权限','Linux','配置定时备份及恢复验证'],
 ['Windows','配置远程管理与事件日志审计','Windows','备份和恢复组策略及关键服务器配置'],
 ['综合','Web 与安全服务综合限时训练','综合','根据验证清单排查服务故障'],
 ['Cisco','配置 IPv6 地址与静态路由','Cisco','验证双栈网络及常见连通性故障'],
 ['Linux','部署容器运行环境与基础应用','Linux','配置容器持久化数据并验证重启'],
 ['Windows','配置域用户批量管理与 PowerShell 自动化','Windows','编写脚本检查服务状态并生成报告'],
 ['Cisco','网络设备配置备份与灾难恢复','Linux','Linux 服务日志分析与故障定位'],
 ['综合','赛题环境部署与网络连通性检查','综合','模拟比赛：按任务书完成服务部署'],
 ['综合','模拟比赛：故障注入与恢复','综合','模拟比赛：功能验证与配置留存'],
 ['综合','月度考核：完成网络及服务器综合任务','综合','月度考核复盘与下月训练目标梳理'],
];
const duties=['夏国金','李玲','李群嘉','肖威','黄道金'];
const modules=['Linux','Windows','Cisco'];
const coaches={Linux:'黄道金',Windows:'李群嘉',Cisco:'肖威'};
const tasks=Object.fromEntries(modules.map(name=>[name,topics.flatMap(t=>[[t[0],t[1]],[t[2],t[3]]]).filter(x=>x[0]===name).map(x=>x[1])]));
const used={Linux:0,Windows:0,Cisco:0};
let n=0;
for (let d=1;d<=30;d++) {
 const row=3+(d-1)*4;
 s.getRange(`G${row}`).values=[[duties[(d-1)%duties.length]]];
 const weekday=new Date(Date.UTC(2026,10,d)).getUTCDay();
 if (weekday===0) {
  for(let k=0;k<4;k++) s.getRange(`D${row+k}`).values=[['休息']];
  s.getRange(`H${row}`).values=[['休息调整，检查实验环境安全。']];
  continue;
 }
 const nextModule=()=>{const name=modules[n++%3]; const i=used[name]++; return [name,tasks[name][i%tasks[name].length],coaches[name]];};
 const morning=nextModule();
 const afternoon=weekday===1?['综合','周例会：汇报训练进度、问题与下周安排','全体']:weekday===6?['English','技术英语专项：阅读赛题、撰写部署说明并进行口头汇报','李玲']:nextModule();
 const rows=[['English','技术英语早读：阅读任务书并整理术语','李玲'],morning,afternoon,['综合','当日训练复盘：整理配置、验证结果与问题清单','全体']];
 for(let k=0;k<4;k++) s.getRange(`D${row+k}:F${row+k}`).values=[rows[k]];
 s.getRange(`H${row}`).values=[['训练结束后保存配置与实验记录。']];
}
const out='E:/04-codes/tms/outputs/01a1a1e4/测试月计划-优化排班.xlsx';
await (await SpreadsheetFile.exportXlsx(wb)).save(out);
try { const img=await wb.render({sheetName:'训练计划',range:'A3:H14',scale:1,format:'png'}); await fs.writeFile('E:/04-codes/tms/outputs/01a1a1e4/preview.png',new Uint8Array(await img.arrayBuffer())); } catch(e) { console.log('render:',String(e)); }
console.log(`saved ${out}; module counts ${JSON.stringify(used)}`);
