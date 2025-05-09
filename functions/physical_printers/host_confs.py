# Configuration for each host type
host_configs: dict[str, [list[str], list[str], dict]] = {
    "prusalink": {
        "endpoints": ["/api/v1/status", "/api/v1/info", "/api/v1/job"],
        "required": ["/api/v1/status", "/api/v1/info"],
        "fields": {
            "progress": {
                "endpoint": "/api/v1/status",
                "path": ["job", "progress"],
                "default": ""
            },
            "state": {
                "endpoint": "/api/v1/status",
                "path": ["printer", "state"],
            },
            "job_name": {
                "endpoint": "/api/v1/job",
                "path": ["file", "display_name"],
                "default": ''
            },
            "job_id": {
                "endpoint": "/api/v1/status",
                "path": ["job", "id"],
                "default": ''
            },
        },
        "commands": {
            "pause_job": {
                "endpoint": "{ip}/api/v1/job/{job_id}/pause",
            },
            "resume_job": {
                "endpoint": "{ip}/api/v1/job/{job_id}/resume",
            }
        }
    },

    "moonraker": {
        "endpoints": ["/printer/objects/query?webhooks&virtual_sdcard&print_stats", "/printer/info"],
        "required": ["/printer/objects/query?webhooks&virtual_sdcard&print_stats", "/printer/info"],
        "fields": {
            "progress": {
                "endpoint": "/printer/objects/query?webhooks&virtual_sdcard&print_stats",
                "path": ["result", "status", "virtual_sdcard", "progress"],
                "transform": lambda v: round(v * 100, 1) if v else '',
            },
            "state": {
                "endpoint": "/printer/objects/query?webhooks&virtual_sdcard&print_stats",
                "path": ["result", "status", "print_stats", "state"],
                "transform": lambda v: v.upper() if v else "UNKNOWN",
            },
        },
    },

    "mainsail": {
        "endpoints": ["/server/info", "/printer/objects/query?virtual_sdcard&print_stats"],
        "required": ["/server/info", "/printer/objects/query?virtual_sdcard&print_stats"],
        "fields": {
            "progress": {
                "endpoint": "/printer/objects/query?virtual_sdcard&print_stats",
                "path": ["result", "status", "virtual_sdcard", "progress"],
                "transform": lambda v: round(float(v) * 100, 1) if v else '',
            },
            "state": {
                "endpoint": "/printer/objects/query?virtual_sdcard&print_stats",
                "path": ["result", "status", "print_stats", "state"],
                "transform": lambda v: v.upper() if v else "UNKNOWN",
            }
        },
    },

    "creality": {
        "endpoints": ["/protocal.csp?fname=Info&opt=main&function=get"],
        "required": ["/protocal.csp?fname=Info&opt=main&function=get"],
        "fields": {
            "progress": {
                "endpoint": "/protocal.csp?fname=Info&opt=main&function=get",
                "path": ["printProgress"],
                "transform": lambda v: round(v, 1) if v else '',
                "default": "",
            },
            "state": {
                "endpoint": "/protocal.csp?fname=Info&opt=main&function=get",
                "path": ["mcu_is_print"],
                "transform": lambda v: ['IDLE', 'PRINTING'][v] if v else "UNKNOWN",
            },
            "job_name": {
                "endpoint": "/protocal.csp?fname=Info&opt=main&function=get",
                "path": ["print"],
                "transform": lambda v: v if v != "localhost" else '',
            },
        },
    }
}