# DB1 最重要待决决策 1 修正计划：no-action 下 CAV/HDV 模型可信性

## 0. 任务契约

本计划是一个可执行的 DB1 implementation audit 修正计划。执行代理应按本文件实施，不需要重新设计 C5 主场景，除非发现代码结构使本计划无法落地；如果无法落地，必须在最终报告中说明阻塞点、涉及文件和最小替代方案。

当前修正目标：

- 修正 DB1/C5 audit 中 no-action 机制不可信的问题。
- 让 C5 成为一个干净的 implementation audit 场景：no-action 下没有可信 reservable edge；full RPMI 通过 CAV front-boundary acceleration 在 action-conditioned rollout 中创造 reservable edge。
- 产出 C7 式 step-level trace，用来核验 action 选择、action-conditioned edge、reservation、ramp guidance 和结果事件是否串起来。

明确禁区：

- 不进入 Prompt 4。
- 不创建 `LOCKED_*` 文件。
- 不做性能 claim。
- 不调 lambda。
- 不改论文主文。
- 不把 R2/R3 repair evidence 升级为 locked evidence。
- 第一阶段只跑 full RPMI，不跑 raw/forced/ablation。
- 第一阶段只研究 CAV-HDV/front acceleration，不扩展 HDV-CAV、CAV-CAV、lane change。

旧 C5/P1b 不再作为机制审计默认场景，因为旧设置 `gap_width=7 m, v=10 m/s, v0=30 m/s` 有两类污染：

- slot validity 没启用论文 4.2 的动态安全距离。
- no-action 下 mainline CAV 从低速朝 30 m/s 自由加速，rear HDV 又因短 gap 急刹，导致 gap 自然变大。

## 1. 执行阶段

### 阶段 A：Slot Validity 对齐论文 4.2

目标文件优先级：

- `src/rpmi/slots.py`
- 与 slot 参数读取相关的配置链路文件，例如 `src/rpmi/scenarios.py`、`src/rpmi/config.py` 或调用方脚本。

必须实现：

- `SlotInventoryParams` 支持 `b_safe`。
- `SlotInventoryParams` 支持分侧/分角色安全时距。第一版至少能表达：
  - `T_front_CAV_following = 1.2 s`
  - `T_rear_HDV_following = 1.6 s`
- 保持向后兼容：已有只传 `T_safe` 的场景不应无故崩溃。若没有分侧参数，可回退到原 `T_safe`。
- `compute_safety_distances(...)` 实现论文 4.2 动态安全距离。

公式：

```text
d_front = d0 + T_front * ramp.v + max(ramp.v - front.v, 0)^2 / (2*b_safe)
d_rear  = d0 + T_rear  * rear.v + max(rear.v - ramp.v, 0)^2 / (2*b_safe)
```

其中：

- `d_front` 表示 ramp 插入后作为后车跟随 front，需要保留的前向安全距离。
- `d_rear` 表示 rear 作为后车跟随插入后的 ramp，需要保留的后向安全距离。
- DB1 第一版中，front side 使用 `T_front_CAV_following=1.2 s`，rear side 使用 `T_rear_HDV_following=1.6 s`。

`compute_feasible_interval(...)` 保持：

```text
lower = rear.x + ramp.length + d_rear
upper = front.x - front.length - d_front
W = upper - lower
```

DB1/C5 主场景的 spatial validity：

- 使用 `W >= 0`。
- `W_min_buffer = 0.0`。
- 固定 residual buffer 不作为主安全阈值；如保留，只能作为鲁棒性/不确定性敏感性配置项。

### 阶段 B：Nominal Dynamics 与场景参数解耦

目标文件优先级：

- `src/rpmi/dynamics.py`
- `src/rpmi/scenarios.py`
- 生成 DB1 C5 audit 场景的脚本或配置。

必须实现：

- mainline CAV nominal 参数可设置为 `v0=20.0 m/s`。
- ramp CAV nominal 参数可设置为 `v0=20.0 m/s`。
- HDV nominal 参数可设置为 `v0=22.0 m/s`。
- 不允许 DB1 C5 场景在 no-action 下继承默认 `v0=30.0 m/s` 后自由加速制造 gap。
- 不允许在 DB1 脚本里硬编码绕过动力学配置。优先通过 `ScenarioConfig`、车辆级 `idm_params` 或已有配置入口表达；如果没有入口，补最小入口。

### 阶段 C：新增 DB1 C5 Audit 场景与脚本

目标：

- 新增或改造一个 DB1 专用 audit 脚本。
- 只跑 full RPMI。
- 不覆盖旧 Prompt 3B/R3-C 文件含义。
- 输出文件名包含 `DB1` 和 `audit`。
- 不输出任何 `LOCKED_*` 文件。

推荐脚本名：

```text
scripts/db1_c5_mechanism_audit.py
```

允许使用其他名称，但必须在最终报告中说明。

场景规格：

```text
scenario_id = DB1-C5-CAV-HDV-FRONTACC-V20-GAP55-TAU35
scenario_family = DB1-C5
mechanism_target = action_conditioned_reservation_front_acc

target_lane = 0
ramp_lane = -1
ramp_end_x = 150.0
boundary_pairs = ["CAV-HDV"]

front vehicle id = 1, role = mainline, type = CAV, lane = 0
rear vehicle id = 2, role = mainline, type = HDV, lane = 0
ramp vehicle id = 100, role = ramp, type = CAV, lane = -1
inner_receiving_gap_count = 1
ramp_count = 1
```

速度和行为模型：

```text
initial mainline speed = 20.0 m/s
initial ramp speed = 20.0 m/s
mainline CAV nominal v0 = 20.0 m/s
ramp CAV nominal v0 = 20.0 m/s
HDV nominal v0 = 22.0 m/s
```

安全距离参数：

```text
d0 = 2.0 m
T_front_CAV_following = 1.2 s
T_rear_HDV_following = 1.6 s
b_safe = 2.5 m/s^2
W_min_buffer = 0.0
production_width_buffer = 0.0
```

时间设置：

```text
dt = 0.5 s
H = 4.0 s
dt_merge = 0.5 s
target designed tau = 3.5 s
T_prod = 3.5 s
```

初始状态：

```text
front_x0 = 100.0
front_length = 5.0
rear_length = 5.0
ramp_length = 5.0

v_front = 20.0
v_rear = 20.0
v_ramp = 20.0

d_front = 2.0 + 1.2*20.0 = 26.0 m
d_rear  = 2.0 + 1.6*20.0 = 34.0 m

required_raw_gap = ramp_length + d_front + d_rear = 65.0 m
initial_raw_gap = 55.0 m
gap_deficit = 10.0 m

rear_x0 = front_x0 - front_length - initial_raw_gap
        = 100.0 - 5.0 - 55.0
        = 40.0

ramp_start_x = 74.0
```

最终第一版车辆表：

| id | role | type | lane | x0 | v0_initial | nominal target |
|---:|---|---|---:|---:|---:|---:|
| 1 | mainline | CAV | 0 | 100.0 | 20.0 | 20.0 |
| 2 | mainline | HDV | 0 | 40.0 | 20.0 | 22.0 |
| 100 | ramp | CAV | -1 | 74.0 | 20.0 | 20.0 |

No-action 目标时刻计算：

```text
tau_target = 3.5

front_x_tau = 100.0 + 20.0*3.5 = 170.0
rear_x_tau  = 40.0 + 20.0*3.5 = 110.0

lower_tau = rear_x_tau + ramp_length + d_rear
          = 110.0 + 5.0 + 34.0
          = 149.0

upper_tau = front_x_tau - front_length - d_front
          = 170.0 - 5.0 - 26.0
          = 139.0

W_tau = upper_tau - lower_tau = -10.0 m

planned_mid_x_tau = (lower_tau + upper_tau) / 2 = 144.0
ramp_start_x = planned_mid_x_tau - ramp_speed*tau_target
             = 144.0 - 20.0*3.5
             = 74.0
```

### 阶段 D：C7 Step-Level Trace

DB1 audit 输出必须能让人类逐步核验代码是否按论文理论运行。trace 至少记录这些节点：

- run metadata：scenario id、代码版本信息、参数摘要、variant=`full_RPMI`。
- candidate time grid：每个 candidate `tau`，至少包括 `1.0/1.5/2.0/2.5/3.0/3.5/4.0`。
- no-action rollout：每个 `tau` 的 front/rear/ramp state，包括 `x/v/a/lane/type`。
- slot/edge validity：`raw_gap`、`ramp_length`、`d_front`、`d_rear`、`lower`、`upper`、`W`、`V_phys_pred`、`V_phys_buffer`、reachability、validity reason、is_reservable。
- candidate action：action id、action type、target vehicle id、start/end time、effective duration、u_front profile、action limits。
- action-conditioned rollout：同 no-action 记录，但要标明 `eval_context=action` 和 `action_id`。
- action effect：front extra displacement、W before/after、selected edge id。
- matching/reservation：selected edge 来源必须是 action-conditioned edge，不能是 stale baseline edge。
- ramp guidance：reservation id、planned merge x/tau、ramp action/guidance 状态。
- result event：是否 service/near-service、是否 hard brake/overlap、merge/result event。

输出格式：

- 可以是 CSV、JSONL 或二者都有。
- 优先选择易读且便于后续审阅的 JSONL + 摘要 CSV。
- 输出路径放在 `outputs/d2_5_theory_alignment/...` 下的 DB1/audit 相关目录。
- 不得创建 `LOCKED_*`。

## 2. 预期行为

### No-Action 预期

```text
tau = 1.0 / 1.5 / 2.0 / 2.5:
  target edge 应仍然明显 invalid；这些时刻不是设计合流目标。

tau = 3.5:
  raw_gap ~= 55.0 m
  d_front ~= 26.0 m
  d_rear ~= 34.0 m
  W ~= -10.0 m
  edge invalid
  fail reason = PHYS_WIDTH_NEGATIVE 或 dynamic safety width insufficient

tau = 4.0:
  若 nominal acceleration 接近 0，raw_gap 应保持约 55.0 m
  W 应继续接近 -10.0 m
  不应自然变成可信 reservable edge
```

No-action 必须避免：

- front CAV 因无 leader 且 `v0=30` 自由加速制造 gap。
- rear HDV 因初始 gap 过小而急刹制造 gap。新场景 `raw_gap=55.0 m`，大于 HDV 在 `v=20 m/s, v0=22 m/s` 下的 IDM 零加速度平衡净距 `s_eq ~= 46.2 m`。
- ramp CAV 继承 mainline 自由流 `v0=30`。
- `W_min_buffer=5` 参与主实验 validity。

### Full RPMI 预期

```text
target edge = ramp 100 between front 1 and rear 2 at tau=3.5
production mode = front_acc
required gap increment ~= 10.0 m
T_prod = 3.5 s
u_front ~= 2*10.0/3.5^2 = 1.63 m/s^2
```

Action-conditioned rollout 预期：

- front CAV 比 no-action 多前移约 10 m。
- selected tau 的 `W` 从负值变为 `>= 0`。
- edge becomes reservable。
- final reservation 必须来自 action-conditioned evaluation。
- matching/reservation 不得使用 stale baseline edge。
- ramp guidance 后至少记录完整链路：action -> edge -> reservation -> guidance -> tau outcome。

## 3. 验证计划

### 单元验证

必须新增或更新相关测试。若项目没有现成测试结构，可新增最小验证脚本，但最终报告必须说明验证方式。

`compute_safety_distances(...)`：

- equal speed 时相对速度项为 0。
- ramp 比 front 快时，`d_front` 增加。
- rear 比 ramp 快时，`d_rear` 增加。
- 闭合速度项等于 `dv^2/(2*b_safe)`。
- 未传分侧参数时，旧 `T_safe` 回退行为可用。

`compute_feasible_interval(...)`：

- `W = raw_gap - ramp.length - d_front - d_rear`。
- `W = 0` 时 deterministic spatial validity 通过。
- `W < 0` 时 invalid。
- `W_min_buffer=0` 时不需要固定 5 m residual buffer。

新 C5 初始状态：

- `raw_gap = 55.0 m`。
- `d_front = 26.0 m`。
- `d_rear = 34.0 m`。
- `W = -10.0 m` at no-action `tau=3.5`。

### 场景验证

旧 C5/P1b 回放验证：

- 启用 `d_front/d_rear` 后，旧 `tau=1.5/2.0/2.5` 不再被当成可信 natural reservation。
- trace 中 invalid 原因来自动态安全距离，而不是旧 `W_min_buffer=5`。

新 DB1 C5 no-action 验证：

- candidate ladder 中 target edge 在 `tau=1.0/1.5/2.0/2.5/3.0/3.5/4.0` 的 no-action 分支均不出现可信 reservable edge。
- front CAV nominal acceleration 接近 0。
- rear HDV 不出现接近硬限制的强制动。
- ramp CAV 不出现朝 `30 m/s` 的自由加速。

新 DB1 C5 full RPMI 验证：

- selected action 为 positive front-boundary CAV acceleration，目标车为 id 1。
- action profile 中 `u_front` 约为 `1.6 m/s^2`，持续到 `tau=3.5 s` 附近，允许实现误差但应同量级。
- action-conditioned `W` 在 selected tau 从负值变为 `>= 0`。
- matching/reservation 使用 action-conditioned edge，不使用 stale baseline edge。
- trace 可以串起 action -> edge -> reservation -> guidance -> result event。

### 回归与边界

- 保持非 DB1 场景对 `W_min_buffer` 的可配置兼容。
- 检查输出不得包含 `LOCKED_*`。
- 最终报告措辞只写 implementation audit / DB1 discussion evidence，不写 locked evidence 或 performance claim。
- 若当前代码实现 full RPMI 不能选出预期 action，不允许临时调 lambda 或改 objective 硬凑；应报告为待审阅的 implementation/objective blocker。

## 4. 交付物

执行代理最终必须交付：

- 修改文件清单。
- 新增/更新的 DB1 audit 脚本路径。
- trace 输出路径。
- 运行的验证命令。
- 验证结果摘要。
- 未完成项或偏离本计划的地方。
- 不得宣称 locked evidence 或性能结论。

## 5. 设计依据与备注

论文第 4.2 节已有正确主公式，本计划不要求改论文主文：

```text
lower = x_j + L_r + d_rear
upper = x_i - L_i - d_front
W = upper - lower
V_phys_pred = 1{W >= 0}
```

动态安全距离的原论文形式：

```text
d_front = d0 + T_safe*v_r + [v_r - v_i]_+^2/(2*b_safe)
d_rear  = d0 + T_safe*v_j + [v_j - v_r]_+^2/(2*b_safe)
```

本计划采用分侧时距是实现层面的场景参数细化，不改变主公式结构。

为什么不用旧 `49 m` 下界：

```text
旧单一 T_safe=1.0 s:
d_front = 2.0 + 1.0*20.0 = 22.0 m
d_rear  = 2.0 + 1.0*20.0 = 22.0 m
required_raw_gap = 5.0 + 22.0 + 22.0 = 49.0 m
```

`49 m` 可作为数学下界或敏感性对照，但不作为 DB1 第一版默认场景。用户反馈理想插入空档应在 60 m 以上，同时要求初始 raw gap 落在 50-60 m 区间，并避免 `W=-0.8` 这种极薄边界。因此默认场景采用 `55.0 m raw gap`、`10.0 m gap deficit`、`tau_target=3.5 s`。

Action 持续时间采用 `3.5 s` 的理由：

- 不把 `tau=1.0 s` 当成默认合流完成时间。对 `raw_gap=55 m`、`gap_deficit=10 m`，1 秒内靠 front CAV 多走 10 m 需要约 `20 m/s^2`，不合理。
- 自然驾驶/车道变换研究中，完整 lane-change/merge maneuver 常见持续时间是数秒量级，而不是 1 秒量级。
- CAV 协同控制文献中，几秒级协调窗口也常见。
- DB1 第一版把 `T_prod=3.5 s` 视为 front CAV 纵向 production action 的短时协同干预窗口，而不是完整人工合流动作的全部持续时间。

外部依据记录：

- IDM 公式中，输入包含自身速度、bumper-to-bumper gap、相对速度；输出是加速度。IDM 将自由加速项和前车导致的制动项相减，动态期望间距随速度、时距和相对速度变化。参考：https://traffic-simulation.de/info/info_IDM.html
- 加州 DMV 驾驶手册建议用 three-second rule 保持安全跟车距离，并提醒有车并入过近时应松开油门创造空间。参考：https://qr.dmv.ca.gov/portal/handbook/california-driver-handbook/safe-driving/
- 一项 freeway merge 驾驶模拟研究报告了不同 CAV 渗透率下的临界 headway gap，大致在 1.7-3.5 s 范围内变化。参考：https://digitalcommons.unf.edu/unf_faculty_publications/538/
- Naturalistic lane-change duration 研究报告 7,192 个单车道变换的平均持续时间约 6.28 s，标准差约 2.0 s。参考：https://journals.sagepub.com/doi/10.1177/154193120204602203
- 上海自然驾驶 lane-change 研究报告 lane-change duration 范围为 0.7-16.1 s。参考：https://www.sciencedirect.com/science/article/pii/S0968090X18315225
- UMTRI 自动高速换道研究选取 2-10 s 的真实 lane-change 事件作为建模样本。参考：https://ccat.umtri.umich.edu/research/u-m/investigation-into-u-s-real-world-lane-change-behavior-for-automated-freeway-driving/
- Cooperative platoon merging 控制研究中，车辆在 3-5 s 时段出现明显加速度/扭矩波动；这支持 DB1 把 3-4 s 视为短时纵向协同干预窗口，而非 1 s 瞬时动作。参考：https://pmc.ncbi.nlm.nih.gov/articles/PMC11556728/
- 在线集中式 MPC platoon merging 研究报告，两车场景中编队形成约 3.5 s，不同规模场景中每次换道/合流大约 2.5-4 s 完成；同时其控制输入约束采用现实车辆加速度限制。参考：https://www.mdpi.com/1424-8220/25/17/5605

