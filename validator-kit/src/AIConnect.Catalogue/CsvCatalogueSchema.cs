using System.Globalization;
using System.Text.Json;
using Microsoft.VisualBasic.FileIO;

namespace AIConnect.Core;

public enum ModelCategory { LightImage, HeavyImage, LightText, HeavyText, Transcription }

public sealed record CsvModel(IReadOnlyDictionary<string,string> Fields) {
    public string this[string key]=>Fields.GetValueOrDefault(key,"");
    public string Id=>this["entry_id"];
    public string Name=>this["model_name"];
    public int Order=>int.Parse(this["category_preference_order"],CultureInfo.InvariantCulture);
    public ModelCategory Category=>CsvCatalogueSchema.Categories[this["category"]];
    public double? Number(string key)=>double.TryParse(this[key],NumberStyles.Float,CultureInfo.InvariantCulture,out var n) ? n : null;
}
public static class CsvCatalogueSchema {
    public const int MaximumBytes=2*1024*1024;
    public static readonly IReadOnlyDictionary<string,ModelCategory> Categories=new Dictionary<string,ModelCategory> {
        ["light_image_generation"]=ModelCategory.LightImage,["heavy_image_generation"]=ModelCategory.HeavyImage,
        ["light_text"]=ModelCategory.LightText,["heavy_text"]=ModelCategory.HeavyText,["transcription"]=ModelCategory.Transcription
    };
    public const string Header="entry_id,model_id,variant_id,model_name,publisher,category,capabilities,parameter_count_billion_total,parameter_count_billion_active,quantization,file_format,runtime_name,runtime_version_or_commit,backend,operating_systems,memory_type,gpu_count,estimated_peak_vram_gib_low,estimated_peak_vram_gib_high,recommended_system_ram_gib,estimated_peak_unified_memory_gib_low,estimated_peak_unified_memory_gib_high,memory_scope,memory_evidence_type,memory_assumptions,offload_mode,image_width,image_height,context_tokens,max_output_tokens,batch_size,recommended_steps,sampler,guidance_scale,flow_shift,model_page_url,variant_repo_url,revision,main_weight_filename,additional_required_files,runtime_support_source_url,recommendation_priority,recommendation_reason,short_description,best_for,limitations,license_id,license_url,access_requirements,checked_date,memory_source_urls,other_source_urls,schema_version,row_status,supersedes_entry_id,architecture,required_gpu_features,required_free_vram_gib,required_free_host_ram_gib,required_free_unified_memory_gib,fit_budget_basis,required_files_json,package_completeness,reviewed_utc,change_note,category_preference_order";
    static readonly string[] Numeric="parameter_count_billion_total,parameter_count_billion_active,gpu_count,estimated_peak_vram_gib_low,estimated_peak_vram_gib_high,recommended_system_ram_gib,estimated_peak_unified_memory_gib_low,estimated_peak_unified_memory_gib_high,image_width,image_height,context_tokens,max_output_tokens,batch_size,recommended_steps,guidance_scale,flow_shift,recommendation_priority,required_free_vram_gib,required_free_host_ram_gib,required_free_unified_memory_gib".Split(',');
    public static IReadOnlyList<CsvModel> Parse(string text) {
        try{return ParseCore(text);}
        catch(Exception e) when(e is JsonException or KeyNotFoundException or InvalidOperationException or FormatException or MalformedLineException){throw new InvalidDataException("Malformed catalogue data: "+e.Message,e);}
    }
    static IReadOnlyList<CsvModel> ParseCore(string text) {
        if(System.Text.Encoding.UTF8.GetByteCount(text)>MaximumBytes)throw new InvalidDataException("CSV exceeds 2 MiB.");
        using var parser=new TextFieldParser(new StringReader(text.TrimStart('\uFEFF'))){HasFieldsEnclosedInQuotes=true,TrimWhiteSpace=false};parser.SetDelimiters(",");
        var headers=parser.ReadFields();if(headers is null || !headers.SequenceEqual(Header.Split(',')))throw new InvalidDataException("Expected the exact 66-column v6 header.");
        var rows=new List<CsvModel>();
        while(!parser.EndOfData) {
            var fields=parser.ReadFields();if(fields is null || fields.Length!=headers.Length || fields.Any(f=>f.Length>50000))throw new InvalidDataException("Invalid CSV row width or field length.");
            var r=new CsvModel(headers.Zip(fields).ToDictionary(p=>p.First,p=>p.Second));
            if(rows.Count>=1000 || r["schema_version"]!="6" || !Categories.ContainsKey(r["category"]) || string.IsNullOrWhiteSpace(r.Id) || string.IsNullOrWhiteSpace(r.Name) || string.IsNullOrWhiteSpace(r["model_id"]) || string.IsNullOrWhiteSpace(r["variant_id"]) || rows.Any(x=>x.Id==r.Id))throw new InvalidDataException("Invalid version, category or model identity.");
            if(!int.TryParse(r["category_preference_order"],out var rank) || rank<1 || rank>1000)throw new InvalidDataException("Invalid category preference order.");
            if(r["row_status"] is not ("research" or "candidate" or "deprecated") || r["package_completeness"] is not ("complete" or "partial" or "unknown") || r["backend"] is not ("CUDA" or "CPU" or "Metal") || r["memory_type"] is not ("dedicated_gpu" or "cpu_only" or "unified_memory"))throw new InvalidDataException("Invalid status or hardware topology.");
            foreach(var key in Numeric)if(r[key]!="" && (r.Number(key) is not {} n || !double.IsFinite(n) || n<0))throw new InvalidDataException("Invalid numeric value: "+key);
            foreach(var prefix in new[]{"estimated_peak_vram_gib_","estimated_peak_unified_memory_gib_"})if(r.Number(prefix+"low") is {} low && r.Number(prefix+"high") is {} high && low>high)throw new InvalidDataException("Memory range is reversed.");
            if(r.Number("required_free_vram_gib") is {} budget && r.Number("estimated_peak_vram_gib_high") is {} peak && budget<peak)throw new InvalidDataException("VRAM budget below peak.");
            if(r.Number("required_free_unified_memory_gib") is {} ub && r.Number("estimated_peak_unified_memory_gib_high") is {} up && ub<up)throw new InvalidDataException("Unified budget below peak.");
            if(r["memory_type"]!="unified_memory" && r["required_free_unified_memory_gib"]!="" || r["memory_type"]!="dedicated_gpu" && r["required_free_vram_gib"]!="" || r["memory_type"]=="unified_memory" && r["required_free_host_ram_gib"]!="")throw new InvalidDataException("Mixed memory topologies.");
            using var files=JsonDocument.Parse(r["required_files_json"]);
            if(files.RootElement.ValueKind!=JsonValueKind.Array || files.RootElement.GetArrayLength()>100)throw new InvalidDataException("Invalid component manifest.");
            foreach(var file in files.RootElement.EnumerateArray()) {
                if(file.ValueKind!=JsonValueKind.Object)throw new InvalidDataException("Invalid component object.");
                var name=file.GetProperty("filename").GetString();var url=file.GetProperty("repository_url").GetString();
                if(string.IsNullOrWhiteSpace(name) || name.StartsWith('/') || name.Contains('\\') || name.Split('/').Any(s=>s is ".." or "." or "") || name.Contains(':') || !Uri.TryCreate(url,UriKind.Absolute,out var uri) || uri.Scheme!="https" || !string.IsNullOrEmpty(uri.UserInfo))throw new InvalidDataException("Invalid component path or repository URL.");
            }
            rows.Add(r);
        }
        if(rows.Count==0)throw new InvalidDataException("Empty catalogue.");
        foreach(var group in rows.GroupBy(r=>r.Category))if(!group.Select(r=>r.Order).Order().SequenceEqual(Enumerable.Range(1,group.Count())))throw new InvalidDataException("Each category needs unique consecutive preference numbers.");
        return rows.OrderBy(r=>r.Category).ThenBy(r=>r.Order).ToArray();
    }
}
