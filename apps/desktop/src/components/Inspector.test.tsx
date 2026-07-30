import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";
import { Inspector } from "./Inspector";

const runtime: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "0.2.0",
  capabilities: ["doctor", "files", "sessions"],
};
const doctor: DoctorPayload = {
  ok: true,
  app_name: "MARA",
  default_user_id: "default",
  index_name: "File Collection",
  index_id: 1,
  llm_default: "local",
  embedding_default: "local",
  file_count: 1,
  session_count: 1,
  graph_cache_dir: "/desktop/state/knowledge_graph/conversations",
  issues: [],
  warnings: [],
};

function render(state: ResourceState<DoctorPayload>) {
  return renderToStaticMarkup(
    <Inspector
      activeTab="run"
      doctor={state}
      onClose={() => undefined}
      onRetryDoctor={() => undefined}
      onSelectTab={() => undefined}
      runtime={runtime}
    />,
  );
}

test("Doctor panel covers loading, success, failed, and degraded states", () => {
  assert.match(render({ status: "loading" }), /正在运行 Doctor/);
  assert.match(render({ status: "success", data: doctor }), /Doctor 通过/);
  assert.match(
    render({ status: "failed", message: "Doctor 暂不可用" }),
    /Doctor 暂不可用/,
  );
  assert.match(
    render({ status: "failed", message: "Doctor 暂不可用" }),
    /重试/,
  );
  assert.match(
    render({
      status: "success",
      data: { ...doctor, ok: false, issues: ["默认索引不可用"] },
    }),
    /默认索引不可用/,
  );
});
