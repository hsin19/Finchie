package statements

import (
	"context"
	"log/slog"
	"os"
	"time"

	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type StatementRepository interface {
	GetStatement(id string) (*Statement, error)
	UpsertStatement(statement *Statement) error
	GetTransactions(statementId string) ([]Transaction, error)
	UpsertTransaction(transactions *Transaction) error
	DeleteTransaction(id string) error
}

func NewRepoFromEnv() StatementRepository {
	mongoURI := os.Getenv("MONGO_URI")
	dbName := os.Getenv("MONGO_DB")

	if mongoURI != "" && dbName != "" {
		db, err := connectMongo(mongoURI, dbName)
		if err != nil {
			slog.Warn("Failed to connect MongoDB. Falling back to in-memory.", "error", err)
		} else {
			slog.Info("Using MongoDB repository", "db", dbName)
			return NewMongoRepo(db)
		}
	}

	slog.Warn("connecting string not found, using in-memory repo")
	return NewInMemoryRepo()
}

func connectMongo(uri, dbName string) (*mongo.Database, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	clientOpts := options.Client().ApplyURI(uri)
	client, err := mongo.Connect(ctx, clientOpts)
	if err != nil {
		return nil, err
	}
	return client.Database(dbName), nil
}
