function PLUGIN:EnvKeys(ctx)
    return {
        { key = "PATH", value = require("file").join_path(ctx.path, "bin") },
    }
end
