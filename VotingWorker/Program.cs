
using System;
using System.Text.Json;
using Npgsql;
using StackExchange.Redis;
using DotNetEnv;

class Program
{
    static void Main(string[] args)
    {
        Env.TraversePath().Load();
        string redisConnectionString = Environment.GetEnvironmentVariable("REDIS_CONNECTION_STRING") ?? "localhost:6379";
        string pgConnectionString = Environment.GetEnvironmentVariable("PG_CONNECTION_STRING") ?? "Host=localhost;Database=voting;Username=kaushalsingh;";

        Console.WriteLine("C# Worker started. Connecting to Redis and PostgreSQL...");

        // Connect to Redis
        var redis = ConnectionMultiplexer.Connect(redisConnectionString);
        var db = redis.GetDatabase();

        Console.WriteLine("Worker is listening for votes on Redis queue 'votes'...");

        while (true)
        {
            try
            {
                var voteValue = db.ListLeftPop("votes");

                if (voteValue.IsNull)
                {
                    System.Threading.Thread.Sleep(500);
                    continue;
                }
                else
                {
                    string voteJson = voteValue.ToString();

                    Console.WriteLine($"Received vote payload: {voteJson}");

                    // Deserialize JSON payload
                    var voteData = JsonSerializer.Deserialize<VotePayload>(voteJson);

                    if (voteData != null)
                    {
                        try
                        {
                            // Insert into PostgreSQL
                            using var conn = new NpgsqlConnection(pgConnectionString);
                            conn.Open();

                            string query = "INSERT INTO votes (candidate_id, user_email) VALUES (@candidate_id, @user_email)";
                            using var cmd = new NpgsqlCommand(query, conn);
                            cmd.Parameters.AddWithValue("candidate_id", voteData.candidate_id);
                            cmd.Parameters.AddWithValue("user_email", voteData.user_email);

                            cmd.ExecuteNonQuery();
                            Console.WriteLine($"Saved vote: Candidate ID {voteData.candidate_id} for {voteData.user_email}");
                        }
                        catch (PostgresException ex) when (ex.SqlState == "23505")
                        {
                            Console.WriteLine($"Duplicate vote rejected for {voteData.user_email}.");
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine($"Database error for {voteData.user_email}: {ex.Message}. Pushing to DLQ.");
                            // Dead Letter Queue
                            db.ListRightPush("votes_dlq", voteJson);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing vote: {ex.Message}");
            }
        }
    }
}

public class VotePayload
{
    public int candidate_id { get; set; }
    public string user_email { get; set; }
}