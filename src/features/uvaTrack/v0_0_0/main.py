import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from jivf import CTest

app = FastAPI(title="CloudEdgeManager Mock Platform")

# --- 模拟平台初始化参数
mock_node_cfg = {
    "heartbeat_config": {
        "check_interval_s": 10,
        "device_timeout_s": 60,
        "server_timeout_s": 60
    },
    "storage_config": {
        "tasks_dir": "./data/tasks",
        "results_dir": "./data/results",
        "telemetry_dir": "./data/telemetry",
        "logs_dir": "./data/logs"
    },
    "auto_register_config": {
        "enabled": True,
        "timeout_s": 60.0
    }
}


def mock_progress_callback(progress="", message="", status=""):
    pass
    # print(f"[Progress {progress}%] Status: {status} | Message: {message}")


# 实例化 CTest (模拟平台加载过程)
# 注意：proc_modules_obj 等参数在 mock 环境下传空或基础对象
ctest_instance = CTest(
    node_cfg=mock_node_cfg,
    process_comm=None,
    proc_modules_obj=None,
    progress_callback=mock_progress_callback
)


@app.post("/api/uvaTrack/CTest/{subfunc}")
async def handle_request(subfunc: str, request: Request):
    """
    统一转发逻辑：根据 URL 中的 subfunc 调用 CTest 类中对应的方法
    """

    # 1. 检查方法是否存在
    if not hasattr(ctest_instance, subfunc):
        raise HTTPException(status_code=404, detail=f"Subfunc '{subfunc}' not found in CTest")

    method = getattr(ctest_instance, subfunc)

    # 2. 检查是否为可调用的公开方法（排除私有方法和属性）
    if not callable(method) or subfunc.startswith("_"):
        raise HTTPException(status_code=403, detail="Access to private methods is forbidden")

    # 3. 解析请求体中的 params
    try:
        params = await request.json()
    except Exception:
        params = {}

    # 4. 执行逻辑并返回结果
    try:

        # CTest 的方法会内部调用 progress_callback 并返回 result 字典
        result = method(params)
        return result
    except KeyError as e:
        return JSONResponse(
            status_code=400,
            content={"code": -1, "msg": f"Missing required parameter: {str(e)}", "data": {}}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": -1, "msg": f"Internal Error: {str(e)}", "data": {}}
        )


if __name__ == "__main__":
    import uvicorn

    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=15000)