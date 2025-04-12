package statements

import (
	"context"
	"errors"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type MongoRepo struct {
	db             *mongo.Database
	statementCol   *mongo.Collection
	transactionCol *mongo.Collection
}

func NewMongoRepo(db *mongo.Database) *MongoRepo {
	return &MongoRepo{
		db:             db,
		statementCol:   db.Collection("statements"),
		transactionCol: db.Collection("transactions"),
	}
}

func (r *MongoRepo) GetStatement(id string) (*Statement, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	var stmt Statement
	err := r.statementCol.FindOne(ctx, bson.M{"_id": id}).Decode(&stmt)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &stmt, nil
}

func (r *MongoRepo) UpsertStatement(statement *Statement) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := r.statementCol.UpdateByID(ctx, statement.ID, bson.M{"$set": statement},
		options.Update().SetUpsert(true))
	return err
}

func (r *MongoRepo) GetTransactions(statementId string) ([]Transaction, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	cursor, err := r.transactionCol.Find(ctx, bson.M{
		"statement_id": statementId,
	})
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)

	var transactions []Transaction
	if err := cursor.All(ctx, &transactions); err != nil {
		return nil, err
	}
	return transactions, nil
}

func (r *MongoRepo) UpsertTransaction(tx *Transaction) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := r.transactionCol.UpdateByID(ctx, tx.ID, bson.M{"$set": tx},
		options.Update().SetUpsert(true))
	return err
}

func (r *MongoRepo) DeleteTransaction(id string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	result, err := r.transactionCol.DeleteOne(ctx, bson.M{"_id": id})
	if err != nil {
		return err
	}
	if result.DeletedCount == 0 {
		return errors.New("transaction not found")
	}
	return nil
}
