using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace AIConnect.Core;

public static class CsvCatalogueIdentity {
    public static string Id(CsvModel row) {
        // Weekly editorial/ranking changes are not new packages. Preserve exact file,
        // revision and runtime/settings changes as distinct acquisition identities.
        var fields="entry_id,model_id,variant_id,category,quantization,file_format,runtime_name,runtime_version_or_commit,backend,architecture,offload_mode,image_width,image_height,context_tokens,max_output_tokens,batch_size,recommended_steps,sampler,guidance_scale,flow_shift,variant_repo_url,revision,main_weight_filename,package_completeness".Split(',');
        using var manifest=JsonDocument.Parse(row["required_files_json"]);
        var files=manifest.RootElement.EnumerateArray().Select(f=>new {
            Slot=Value(f,"slot"),Repository=Value(f,"repository_url"),File=Value(f,"filename"),Revision=Value(f,"revision"),Size=Value(f,"size_bytes"),Hash=Value(f,"sha256"),Shard=Value(f,"shard_index"),Shards=Value(f,"shard_count")
        }).OrderBy(f=>f.Slot,StringComparer.Ordinal).ThenBy(f=>f.Repository,StringComparer.Ordinal).ThenBy(f=>f.File,StringComparer.Ordinal);
        var key=JsonSerializer.Serialize(new {Fields=fields.Select(k=>new {Key=k,Value=row[k]}),Files=files});
        return "csv-download-"+Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(key))).ToLowerInvariant();
    }
    static string? Value(JsonElement file,string key)=>file.TryGetProperty(key,out var value) && value.ValueKind!=JsonValueKind.Null ? value.ToString() : null;
}
