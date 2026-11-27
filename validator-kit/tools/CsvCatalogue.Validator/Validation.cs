using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using AIConnect.Core;
namespace CsvCatalogue.Validator;

public sealed record Diagnostic(string Severity,string Code,string Location,string Message);
public sealed record Change(string EntryId,string Kind,string[] Fields);
public sealed class Report {
    public string ToolVersion {get;}="1.1.0";
    public string SourceCheckpoint {get;}="b1b5750 (minimal-library revision; see kit SHA256SUMS)";
    public string PolicyVersion {get;}="manager-capacity-2x-1";
    public int SchemaVersion {get;}=6;
    public string Kind {get;init;}="";
    public bool PublicationApproved {get;}=false;
    public bool Valid=>Diagnostics.All(d=>d.Severity!="error");
    public long Bytes {get;set;}
    public string Sha256 {get;set;}="";
    public long? PreviousBytes {get;set;}
    public string? PreviousSha256 {get;set;}
    public List<Diagnostic> Diagnostics {get;}=[];
    public List<Change> Changes {get;}=[];
}
public static class Validation {
    public static byte[] ReadBounded(string path,int maximum) {
        using var stream=File.OpenRead(path);
        if(stream.Length>maximum)throw new InvalidDataException($"Input exceeds {maximum} bytes.");
        using var output=new MemoryStream();var buffer=new byte[8192];int count;
        while((count=stream.Read(buffer))>0){if(output.Length+count>maximum)throw new InvalidDataException($"Input exceeds {maximum} bytes.");output.Write(buffer,0,count);}
        return output.ToArray();
    }
    public static IReadOnlyList<CsvModel> Parse(byte[] bytes) {
        if(bytes.Length>CsvCatalogueSchema.MaximumBytes)throw new InvalidDataException("CSV exceeds production byte limit.");
        return CsvCatalogueSchema.Parse(new UTF8Encoding(false,true).GetString(bytes));
    }
    public static Report Run(string csv,string kind,string? previous=null,string? manifest=null) {
        var result=new Report{Kind=kind};
        if(kind is not ("synthetic" or "candidate"))throw new ArgumentException("Explicit input kind required.");
        if(kind=="synthetic")result.Diagnostics.Add(new("warning","SYNTHETIC","$","Synthetic test input: never publish. Manifest promotion is prohibited."));
        string location="csv:$";
        try {
            var bytes=ReadBounded(csv,CsvCatalogueSchema.MaximumBytes);result.Bytes=bytes.LongLength;result.Sha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            var rows=Parse(bytes);
            foreach(var row in rows.OrderBy(r=>r.Id,StringComparer.Ordinal)) {
                var at="entry_id="+row.Id;
                if(row["row_status"]!="candidate")result.Diagnostics.Add(new("warning","RESEARCH_ONLY",at+"/row_status","Not recommendation eligible; catalogue validity does not establish runtime support."));
                if(row["memory_scope"]!="complete_pipeline" || row["memory_evidence_type"] is "" or "unknown" || row["fit_budget_basis"]=="")result.Diagnostics.Add(new("warning","CAPACITY_UNKNOWN",at+"/memory_evidence_type","Missing complete-pipeline memory evidence/basis; not a hardware match."));
                if(row["checked_date"]=="" || row["reviewed_utc"]=="" || row["runtime_support_source_url"]=="" || row["memory_source_urls"]=="")result.Diagnostics.Add(new("warning","SOURCE_GAPS",at,"Source/date fields incomplete. Parser permits this; producer review required."));
                using var files=JsonDocument.Parse(row["required_files_json"]);
                int i=0;
                foreach(var f in files.RootElement.EnumerateArray()) {
                    bool pinned=f.TryGetProperty("revision",out var rev) && System.Text.RegularExpressions.Regex.IsMatch(rev.ToString(),"\\A[0-9a-fA-F]{40}\\z");
                    bool hash=f.TryGetProperty("sha256",out var sha) && System.Text.RegularExpressions.Regex.IsMatch(sha.ToString(),"\\A[0-9a-fA-F]{64}\\z");
                    bool size=f.TryGetProperty("size_bytes",out var sz) && sz.ValueKind==JsonValueKind.Number && sz.TryGetInt64(out var n) && n>0;
                    if(!pinned || !hash || !size)result.Diagnostics.Add(new("warning","UNRESOLVED_FILE",at+"/required_files_json/"+i,"Exact revision, positive size and SHA-256 are not all resolved. No weight bytes checked."));
                    i++;
                }
                if(i==0 || row["package_completeness"]!="complete")result.Diagnostics.Add(new("warning","INCOMPLETE_PACKAGE",at+"/required_files_json","Research data only; complete required files not established."));
            }
            if(previous is not null) {
                location="previous:$";var previousBytes=ReadBounded(previous,CsvCatalogueSchema.MaximumBytes);
                result.PreviousBytes=previousBytes.LongLength;result.PreviousSha256=Convert.ToHexString(SHA256.HashData(previousBytes)).ToLowerInvariant();
                var old=Parse(previousBytes).ToDictionary(r=>r.Id);
                var next=rows.ToDictionary(r=>r.Id);
                foreach(var id in old.Keys.Union(next.Keys).Order(StringComparer.Ordinal)) {
                    if(!old.TryGetValue(id,out var a)){result.Changes.Add(new(id,"added",[]));continue;}
                    if(!next.TryGetValue(id,out var b)){result.Changes.Add(new(id,"withdrawn",[]));continue;}
                    var fields=CsvCatalogueSchema.Header.Split(',').Where(k=>a[k]!=b[k]).ToArray();
                    if(fields.Length==0)continue;
                    var acquisition=CsvCatalogueIdentity.Id(a)!=CsvCatalogueIdentity.Id(b);
                    result.Changes.Add(new(id,acquisition?"files-runtime-settings-identity":fields.Contains("row_status") && b["row_status"]=="deprecated"?"withdrawn":fields.Contains("category_preference_order")?"ranking-editorial":"metadata-policy",fields));
                }
            }
            if(manifest is not null) {
                location="manifest:$";
                if(kind=="synthetic")throw new InvalidDataException("Synthetic input cannot validate a publication manifest.");
                var contract=CsvFeedContract.Parse(ReadBounded(manifest,CsvFeedContract.MaximumManifestBytes),DateTimeOffset.UtcNow);
                if(contract.SizeBytes!=result.Bytes || !contract.Sha256.Equals(result.Sha256,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Manifest size/hash differs from exact CSV bytes.");
            }
        } catch(Exception e) when(e is InvalidDataException or JsonException or ArgumentException or KeyNotFoundException or InvalidOperationException or FormatException) {
            result.Diagnostics.Add(new("error","INPUT_REJECTED",location,e.Message));
        }
        return result;
    }
}
