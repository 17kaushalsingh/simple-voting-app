
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

        try
        {
            db.StreamCreateConsumerGroup("votes", "worker-group", "0-0", createStream: true);
            Console.WriteLine("Consumer group 'worker-group' ensured.");
        }
        catch (RedisServerException ex) when (ex.Message.Contains("BUSYGROUP"))
        {
            // Group already exists, ignore
        }

        Console.WriteLine("Worker is listening for votes on Redis Stream 'votes'...");

        // First process any unacknowledged messages (crash recovery), then block for new ones
        string nextId = "0-0"; 
        bool recovering = true;

        while (true)
        {
            try
            {
                var messages = db.StreamReadGroup("votes", "worker-group", "worker-1", recovering ? nextId : ">", count: 1);

                if (messages.Length == 0)
                {
                    if (recovering) 
                    {
                        recovering = false; // Finished recovering old messages, switch to polling new ones
                        continue;
                    }
                    System.Threading.Thread.Sleep(500);
                    continue;
                }
                else
                {
                    var message = messages[0];
                    if (recovering) nextId = message.Id; // Update cursor for recovery mode
                    
                    // The payload is stored in the 'payload' field
                    string voteJson = message.Values[0].Value.ToString();

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
                            
                            using var transaction = conn.BeginTransaction();

                            string insertQuery = "INSERT INTO votes (candidate_id, user_email) VALUES (@candidate_id, @user_email)";
                            using var insertCmd = new NpgsqlCommand(insertQuery, conn, transaction);
                            insertCmd.Parameters.AddWithValue("candidate_id", voteData.candidate_id);
                            insertCmd.Parameters.AddWithValue("user_email", voteData.user_email);
                            insertCmd.ExecuteNonQuery();

                            string updateQuery = "UPDATE candidates SET vote_count = vote_count + 1 WHERE id = @candidate_id";
                            using var updateCmd = new NpgsqlCommand(updateQuery, conn, transaction);
                            updateCmd.Parameters.AddWithValue("candidate_id", voteData.candidate_id);
                            updateCmd.ExecuteNonQuery();
                            
                            transaction.Commit();
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
                    
                    // Acknowledge the message so it is removed from the Pending Entries List (PEL)
                    db.StreamAcknowledge("votes", "worker-group", message.Id);
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